require('dotenv').config();
const express = require('express');
const path = require('path');
const fs = require('fs');
const Anthropic = require('@anthropic-ai/sdk');

const app = express();
app.use(express.json());
app.use(express.static(path.join(__dirname, 'frontend')));
app.use('/staff', express.static(path.join(__dirname, 'staff')));

// --- Load static data once at startup ---
const systemPrompt = fs.readFileSync(path.join(__dirname, 'prompts', 'system-prompt.md'), 'utf8');
const menu = JSON.parse(fs.readFileSync(path.join(__dirname, 'data', 'menu.json'), 'utf8'));
const promotions = JSON.parse(fs.readFileSync(path.join(__dirname, 'data', 'promotions.json'), 'utf8'));

const anthropic = new Anthropic({ apiKey: process.env.ANTHROPIC_API_KEY });

// DEV-ONLY STORAGE WARNING:
// orders.json is a flat-file store for local development only.
// In production, replace with a real database (PostgreSQL, MongoDB, etc.).
const ORDERS_FILE = path.join(__dirname, 'data', 'orders.json');

function readOrders() {
  return JSON.parse(fs.readFileSync(ORDERS_FILE, 'utf8'));
}
function writeOrders(orders) {
  fs.writeFileSync(ORDERS_FILE, JSON.stringify(orders, null, 2));
}
function generateOrderId() {
  const num = String(Math.floor(1000 + Math.random() * 9000));
  return `AR-${num}`;
}

// --- In-memory session state (keyed by sessionId) ---
const sessions = {};

function getSession(sessionId) {
  if (!sessions[sessionId]) {
    sessions[sessionId] = {
      items: [],
      orderType: null,
      customer: { name: null, phone: null, address: null, unit: null, instructions: null },
      discount: { code: null, type: null, value: 0, freeDelivery: false },
      confirmed: false,
      status: 'NEW',
    };
  }
  return sessions[sessionId];
}

// --- Tool definitions for Claude ---
const tools = [
  {
    name: 'getMenu',
    description: 'Returns the full Al Roshan menu with IDs, names, prices, and options.',
    input_schema: { type: 'object', properties: {}, required: [] },
  },
  {
    name: 'addItemToCart',
    description: 'Adds a menu item to the cart. Must validate item ID against menu.json.',
    input_schema: {
      type: 'object',
      properties: {
        itemId: { type: 'string', description: 'Menu item ID (e.g. AR001)' },
        quantity: { type: 'number', description: 'Number of this item to add' },
        selectedOptions: { type: 'object', description: 'Selected options for the item (e.g. {serving: "Wrap in pita"})' },
      },
      required: ['itemId', 'quantity'],
    },
  },
  {
    name: 'modifyItem',
    description: 'Modifies an existing cart item (quantity, options).',
    input_schema: {
      type: 'object',
      properties: {
        itemId: { type: 'string' },
        quantity: { type: 'number' },
        selectedOptions: { type: 'object' },
      },
      required: ['itemId'],
    },
  },
  {
    name: 'removeItem',
    description: 'Removes an item or reduces its quantity from the cart.',
    input_schema: {
      type: 'object',
      properties: {
        itemId: { type: 'string' },
        quantity: { type: 'number', description: 'If omitted, removes entire item' },
      },
      required: ['itemId'],
    },
  },
  {
    name: 'viewCart',
    description: 'Returns a structured summary of the current cart with itemized prices.',
    input_schema: { type: 'object', properties: {}, required: [] },
  },
  {
    name: 'applyPromotion',
    description: 'Applies a promotion code. Only valid active codes from promotions.json are accepted.',
    input_schema: {
      type: 'object',
      properties: { code: { type: 'string' } },
      required: ['code'],
    },
  },
  {
    name: 'setOrderType',
    description: 'Sets the order type to pickup or delivery.',
    input_schema: {
      type: 'object',
      properties: { type: { type: 'string', enum: ['pickup', 'delivery'] } },
      required: ['type'],
    },
  },
  {
    name: 'setCustomerDetails',
    description: 'Records customer name, phone, address (for delivery), and instructions.',
    input_schema: {
      type: 'object',
      properties: {
        name: { type: 'string' },
        phone: { type: 'string' },
        address: { type: 'string' },
        unit: { type: 'string' },
        instructions: { type: 'string' },
      },
      required: ['name'],
    },
  },
  {
    name: 'confirmOrder',
    description: 'Called ONLY when the customer has explicitly said YES and confirmed all details. Saves the order to the database.',
    input_schema: { type: 'object', properties: {}, required: [] },
  },
];

// --- Deterministic order calculation ---
function calculateTotals(session) {
  const TAX_RATE = 0.05;
  const DELIVERY_FEE = 3.99;

  let subtotal = 0;
  for (const item of session.items) {
    subtotal += item.price * item.quantity;
  }

  let discountAmount = 0;
  let freeDelivery = session.discount.freeDelivery;

  if (session.discount.type === 'percentage') {
    discountAmount = subtotal * (session.discount.value / 100);
  }

  const discountedSubtotal = subtotal - discountAmount;
  const tax = discountedSubtotal * TAX_RATE;
  const deliveryFee = session.orderType === 'delivery' && !freeDelivery ? DELIVERY_FEE : 0;
  const grandTotal = discountedSubtotal + tax + deliveryFee;

  return {
    subtotal: +subtotal.toFixed(2),
    discountAmount: +discountAmount.toFixed(2),
    tax: +tax.toFixed(2),
    deliveryFee: +deliveryFee.toFixed(2),
    grandTotal: +grandTotal.toFixed(2),
  };
}

// --- Tool execution ---
function executeTool(toolName, toolInput, session) {
  switch (toolName) {
    case 'getMenu':
      return { menu: menu.filter(i => i.available) };

    case 'addItemToCart': {
      const menuItem = menu.find(i => i.id === toolInput.itemId && i.available);
      if (!menuItem) return { error: `Item ${toolInput.itemId} not found on menu.` };
      const existing = session.items.find(i => i.id === toolInput.itemId);
      if (existing) {
        existing.quantity += toolInput.quantity || 1;
        if (toolInput.selectedOptions) existing.selectedOptions = toolInput.selectedOptions;
      } else {
        session.items.push({
          id: menuItem.id,
          name: menuItem.name,
          price: menuItem.price,
          quantity: toolInput.quantity || 1,
          selectedOptions: toolInput.selectedOptions || {},
        });
      }
      return { success: true, cart: session.items };
    }

    case 'modifyItem': {
      const idx = session.items.findIndex(i => i.id === toolInput.itemId);
      if (idx === -1) return { error: 'Item not in cart.' };
      if (toolInput.quantity !== undefined) session.items[idx].quantity = toolInput.quantity;
      if (toolInput.selectedOptions) session.items[idx].selectedOptions = toolInput.selectedOptions;
      return { success: true, cart: session.items };
    }

    case 'removeItem': {
      const idx = session.items.findIndex(i => i.id === toolInput.itemId);
      if (idx === -1) return { error: 'Item not in cart.' };
      if (toolInput.quantity && session.items[idx].quantity > toolInput.quantity) {
        session.items[idx].quantity -= toolInput.quantity;
      } else {
        session.items.splice(idx, 1);
      }
      return { success: true, cart: session.items };
    }

    case 'viewCart': {
      const totals = calculateTotals(session);
      return { items: session.items, totals, orderType: session.orderType, customer: session.customer };
    }

    case 'applyPromotion': {
      const promo = promotions.find(
        p => p.code.toUpperCase() === toolInput.code.toUpperCase() && p.active
      );
      if (!promo) return { error: 'Promotion code not recognized or not active.' };
      const totals = calculateTotals(session);
      if (promo.minOrderAmount > 0 && totals.subtotal < promo.minOrderAmount) {
        return { error: `Minimum order of $${promo.minOrderAmount} required for this promotion.` };
      }
      session.discount = {
        code: promo.code,
        type: promo.type,
        value: promo.value,
        freeDelivery: promo.type === 'free_delivery',
      };
      return { success: true, promotion: promo };
    }

    case 'setOrderType':
      session.orderType = toolInput.type;
      return { success: true, orderType: session.orderType };

    case 'setCustomerDetails':
      Object.assign(session.customer, toolInput);
      return { success: true, customer: session.customer };

    case 'confirmOrder': {
      if (session.items.length === 0) return { error: 'Cart is empty.' };
      if (!session.orderType) return { error: 'Order type (pickup/delivery) not set.' };
      if (!session.customer.name) return { error: 'Customer name required.' };
      if (session.orderType === 'delivery' && !session.customer.address) {
        return { error: 'Delivery address required.' };
      }

      const totals = calculateTotals(session);
      const order = {
        id: generateOrderId(),
        timestamp: new Date().toISOString(),
        status: 'NEW',
        orderType: session.orderType,
        customer: session.customer,
        items: session.items,
        discount: session.discount,
        totals,
      };

      const orders = readOrders();
      orders.push(order);
      writeOrders(orders);
      session.confirmed = true;

      return { success: true, orderId: order.id, totals, status: 'NEW' };
    }

    default:
      return { error: `Unknown tool: ${toolName}` };
  }
}

// --- POST /api/chat ---
app.post('/api/chat', async (req, res) => {
  const { message, history, sessionId } = req.body;

  if (!message || typeof message !== 'string') {
    return res.status(400).json({ error: 'Missing or invalid message.' });
  }

  const sid = sessionId || 'default';
  const session = getSession(sid);

  // Build grounding context: system prompt + live menu + active promotions
  const grounding = `
${systemPrompt}

---
## Current Menu (source of truth — use this for all prices and items)
${JSON.stringify(menu.filter(i => i.available), null, 2)}

## Active Promotions
${JSON.stringify(promotions.filter(p => p.active), null, 2)}
`.trim();

  // Sliding window: keep last 10 messages
  const priorMessages = Array.isArray(history) ? history.slice(-10) : [];
  const messages = [
    ...priorMessages,
    { role: 'user', content: message },
  ];

  try {
    let response = await anthropic.messages.create({
      model: 'claude-sonnet-4-5',
      max_tokens: 1024,
      system: grounding,
      tools,
      messages,
    });

    // Agentic tool-call loop
    while (response.stop_reason === 'tool_use') {
      const assistantContent = response.content;
      const toolResults = [];

      for (const block of assistantContent) {
        if (block.type === 'tool_use') {
          const result = executeTool(block.name, block.input, session);
          toolResults.push({
            type: 'tool_result',
            tool_use_id: block.id,
            content: JSON.stringify(result),
          });
        }
      }

      messages.push({ role: 'assistant', content: assistantContent });
      messages.push({ role: 'user', content: toolResults });

      response = await anthropic.messages.create({
        model: 'claude-sonnet-4-5',
        max_tokens: 1024,
        system: grounding,
        tools,
        messages,
      });
    }

    // Extract text reply
    const replyBlock = response.content.find(b => b.type === 'text');
    const reply = replyBlock ? replyBlock.text : "I'm sorry, I couldn't process that. Please try again.";

    res.json({ reply, sessionId: sid });
  } catch (err) {
    console.error('Claude API error:', err.message);
    res.status(500).json({ reply: "I'm having trouble connecting right now. Please try again in a moment." });
  }
});

// --- GET /api/orders — staff: list all orders ---
app.get('/api/orders', (req, res) => {
  res.json(readOrders());
});

// --- PUT /api/orders/:id/status — staff: update order status ---
app.put('/api/orders/:id/status', (req, res) => {
  const { id } = req.params;
  const { status } = req.body;
  const validStatuses = ['NEW', 'PREPARING', 'READY', 'COMPLETED'];
  if (!validStatuses.includes(status)) {
    return res.status(400).json({ error: 'Invalid status.' });
  }
  const orders = readOrders();
  const order = orders.find(o => o.id === id);
  if (!order) return res.status(404).json({ error: 'Order not found.' });
  order.status = status;
  writeOrders(orders);
  res.json({ success: true, order });
});

// --- Serve frontend for any unmatched routes ---
app.get('*', (req, res) => {
  res.sendFile(path.join(__dirname, 'frontend', 'index.html'));
});

const PORT = process.env.PORT || 3000;
app.listen(PORT, () => console.log(`Al Roshan Restaurant server running on http://localhost:${PORT}`));
