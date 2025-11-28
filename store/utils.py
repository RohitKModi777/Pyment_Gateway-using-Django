from __future__ import annotations

from typing import List

from django.http import HttpRequest

from .models import Cart, CartItem, Product


def get_cart(request: HttpRequest) -> Cart:
    if request.user.is_authenticated:
        cart, _ = Cart.objects.get_or_create(user=request.user)
    else:
        if not request.session.session_key:
            request.session.create()
        cart, _ = Cart.objects.get_or_create(session_key=request.session.session_key)
    return cart


def add_to_cart(request: HttpRequest, product_id: int, qty: int = 1) -> None:
    cart = get_cart(request)
    product = Product.objects.get(id=product_id)
    item, created = CartItem.objects.get_or_create(cart=cart, product=product)
    if not created:
        item.qty += qty
        item.save()
    else:
        item.qty = qty
        item.save()


def remove_from_cart(request: HttpRequest, product_id: int) -> None:
    cart = get_cart(request)
    CartItem.objects.filter(cart=cart, product_id=product_id).delete()


def decrease_from_cart(request: HttpRequest, product_id: int) -> None:
    cart = get_cart(request)
    try:
        item = CartItem.objects.get(cart=cart, product_id=product_id)
        item.qty -= 1
        if item.qty <= 0:
            item.delete()
        else:
            item.save()
    except CartItem.DoesNotExist:
        pass


def clear_cart(request: HttpRequest) -> None:
    cart = get_cart(request)
    cart.items.all().delete()


def cart_items(request: HttpRequest) -> List[CartItem]:
    cart = get_cart(request)
    return list(cart.items.select_related("product").all())


def cart_total_cents(request: HttpRequest) -> int:
    cart = get_cart(request)
    return cart.total_cents

