from django.test import TestCase, Client
from django.contrib.auth import get_user_model
from django.urls import reverse
from unittest.mock import patch
from store.models import Product, Cart, CartItem, PreviousCartItem, Order

User = get_user_model()

class CartTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='testuser', password='password')
        self.product = Product.objects.create(
            title='Test Product', 
            price_cents=1000, 
            inventory=10,
            slug='test-product'
        )
        self.client = Client()
        self.client.login(username='testuser', password='password')

    def test_add_to_cart(self):
        response = self.client.post(reverse('store:cart-add', args=[self.product.id]), {'qty': 1})
        self.assertEqual(response.status_code, 302)
        cart = Cart.objects.get(user=self.user)
        self.assertEqual(cart.items.count(), 1)
        self.assertEqual(cart.items.first().qty, 1)

    def test_increase_quantity(self):
        self.client.post(reverse('store:cart-add', args=[self.product.id]), {'qty': 1})
        response = self.client.post(reverse('store:cart-increase', args=[self.product.id]))
        cart = Cart.objects.get(user=self.user)
        self.assertEqual(cart.items.first().qty, 2)

    def test_decrease_quantity(self):
        self.client.post(reverse('store:cart-add', args=[self.product.id]), {'qty': 2})
        response = self.client.post(reverse('store:cart-decrease', args=[self.product.id]))
        cart = Cart.objects.get(user=self.user)
        self.assertEqual(cart.items.first().qty, 1)

    def test_remove_item_moves_to_history(self):
        self.client.post(reverse('store:cart-add', args=[self.product.id]), {'qty': 1})
        response = self.client.post(reverse('store:cart-remove', args=[self.product.id]))
        cart = Cart.objects.get(user=self.user)
        self.assertEqual(cart.items.count(), 0)
        self.assertTrue(PreviousCartItem.objects.filter(user=self.user, product=self.product).exists())

    def test_decrease_to_zero_moves_to_history(self):
        self.client.post(reverse('store:cart-add', args=[self.product.id]), {'qty': 1})
        response = self.client.post(reverse('store:cart-decrease', args=[self.product.id]))
        cart = Cart.objects.get(user=self.user)
        self.assertEqual(cart.items.count(), 0)
        self.assertTrue(PreviousCartItem.objects.filter(user=self.user, product=self.product).exists())

    def test_restore_item(self):
        PreviousCartItem.objects.create(user=self.user, product=self.product)
        prev_item = PreviousCartItem.objects.get(user=self.user, product=self.product)
        response = self.client.post(reverse('store:cart-history-restore', args=[prev_item.id]))
        cart = Cart.objects.get(user=self.user)
        self.assertEqual(cart.items.count(), 1)
        self.assertFalse(PreviousCartItem.objects.filter(id=prev_item.id).exists())

class RazorpayTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='testuser', password='password')
        self.product = Product.objects.create(
            title='Test Product', 
            price_cents=1000, 
            inventory=10,
            slug='test-product'
        )
        self.client = Client()
        self.client.login(username='testuser', password='password')
        self.client.post(reverse('store:cart-add', args=[self.product.id]), {'qty': 1})

    @patch('store.views.create_razorpay_order')
    def test_create_order(self, mock_create_order):
        mock_create_order.return_value = {
            'id': 'order_mock_123',
            'amount': 1000,
            'currency': 'INR'
        }
        response = self.client.post(reverse('store:checkout-create-order'))
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn('order_id', data)
        self.assertIn('amount', data)
        self.assertTrue(Order.objects.filter(id=data['order_uuid']).exists())
