import pathlib
import re

# Read the backup file
backup = pathlib.Path('store/views.py.backup')
if not backup.exists():
    print('ERROR: Backup file not found!')
    exit(1)

content = backup.read_text(encoding='utf-8')

# Check if cart function exists
if 'def cart(request):' not in content:
    print('ERROR: Cart function not found in backup!')
    exit(1)

# Find and replace the cart function
cart_pattern = r'@login_required\s+def cart\(request\):.*?(?=\n@|\nclass |\ndef [a-z_]+\()'
cart_replacement = '''@login_required
def cart(request):
    """View shopping cart."""
    cart_items = CartItem.objects.filter(cart__user=request.user).select_related("product")
    previous_items = PreviousCartItem.objects.filter(user=request.user).select_related("product")[:10]  # Limit to 10 most recent
    
    total = sum(item.line_total_cents for item in cart_items) / 100  # Convert cents to rupees
    
    return render(
        request,
        "store/cart.html",
        {
            "cart_items": cart_items,
            "previous_items": previous_items,
            "total": total
        },
    )


'''

content = re.sub(cart_pattern, cart_replacement, content, flags=re.DOTALL)

# Find and replace the restore redirect
content = content.replace('return redirect("store:previous-cart")', 'return redirect("store:cart")')

# Write the corrected file
pathlib.Path('store/views.py').write_text(content, encoding='utf-8')
print('SUCCESS: File restored with previous_items support')
print('- Added previous_items query to cart view')
print('- Changed restore redirect to stay on cart page')
