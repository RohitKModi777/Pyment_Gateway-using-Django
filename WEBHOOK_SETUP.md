# Razorpay Webhook Setup Guide

This guide will help you configure Razorpay webhooks for your PayDemo project.

## 1. Prerequisites

- Razorpay Account (Test Mode)
- `ngrok` installed (for local development)
- Django server running

## 2. Local Development Setup

Since Razorpay cannot send webhooks to `localhost`, you need to expose your local server using **ngrok**.

### Step 1: Start Django Server
```bash
python manage.py runserver
```

### Step 2: Start ngrok
In a new terminal:
```bash
ngrok http 8000
```
Copy the HTTPS URL (e.g., `https://abc123xyz.ngrok.io`).

## 3. Configure Razorpay Dashboard

1. Log in to [Razorpay Dashboard](https://dashboard.razorpay.com).
2. Ensure you are in **Test Mode**.
3. Go to **Settings** → **Webhooks**.
4. Click **+ Add New Webhook**.
5. **Webhook URL**: Paste your ngrok URL + `/webhooks/razorpay/`
   - Example: `https://abc123xyz.ngrok.io/webhooks/razorpay/`
6. **Secret**: Enter a strong secret or let Razorpay generate one.
   - **Important**: Copy this secret immediately!
7. **Active Events**: Select the following:
   - `payment.captured`
   - `payment.failed`
   - `payment.authorized`
   - `refund.processed`
   - `order.paid`
8. Click **Create Webhook**.

## 4. Update Environment Variables

Update your `.env` file with the webhook secret:

```env
WEBHOOK_SECRET=your_copied_secret_here
```

Restart your Django server to apply changes.

## 5. Testing

### Option A: Using Management Command (Local Only)
You can simulate a webhook event without ngrok:

```bash
# Simulate payment captured
python manage.py test_webhook --event payment.captured --order-id <your-order-id>

# Simulate payment failed
python manage.py test_webhook --event payment.failed --order-id <your-order-id>
```

### Option B: End-to-End Test
1. Go to your app's checkout page.
2. Make a payment using a test card.
3. Check the **Webhook Inspector** at `http://localhost:8000/webhooks/inspector/`.
4. Verify the order status is updated to "Paid".

## 6. Troubleshooting

- **Signature Verification Failed**: Check if `WEBHOOK_SECRET` in `.env` matches the one in Razorpay Dashboard.
- **404 Error**: Ensure the webhook URL in Razorpay ends with `/webhooks/razorpay/`.
- **No Webhook Received**: Ensure ngrok is running and the URL is correct. Check Razorpay Webhook Logs.

## 7. Production Deployment

For production:
1. Use your actual domain name (e.g., `https://yourdomain.com/webhooks/razorpay/`).
2. Use the **Live Mode** secret from Razorpay.
3. Ensure `DEBUG=False` in settings.
