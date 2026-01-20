#!/usr/bin/env python
"""
Test script to verify Order creation with organization assignment
"""
import os
import sys
import django

# Setup Django
sys.path.insert(0, os.path.dirname(__file__))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'myproject.settings')
django.setup()

from django.contrib.auth.models import User
from sylvia.models import Organization, UserProfile, Depot, Product, Dealer, Vehicle, Order, OrderItem
from sylvia.middleware import set_current_organization


def test_order_creation():
    """Test that Order creation works with organization auto-assignment"""

    print("Setting up test data...")

    # Get or create test organization
    org, _ = Organization.objects.get_or_create(
        slug='default',
        defaults={'name': 'Default Organization', 'is_active': True}
    )
    print(f"✓ Organization: {org.name}")

    # Get or create test user
    user, _ = User.objects.get_or_create(
        username='testuser',
        defaults={'email': 'test@example.com'}
    )

    # Create or get user profile
    profile, _ = UserProfile.objects.get_or_create(
        user=user,
        defaults={'organization': org}
    )
    print(f"✓ User: {user.username}")

    # Set organization context (simulating middleware)
    set_current_organization(org)
    print(f"✓ Organization context set to: {org.name}\n")

    # Create test data with explicit organization
    depot, _ = Depot.objects.get_or_create(
        organization=org,
        code='TEST01',
        defaults={
            'name': 'Test Depot',
            'city': 'Test City',
            'state': 'Test State'
        }
    )
    print(f"✓ Depot created: {depot}")

    product, _ = Product.objects.get_or_create(
        organization=org,
        code='PROD01',
        defaults={
            'name': 'Test Product',
            'unit': 'MT'
        }
    )
    print(f"✓ Product created: {product}")

    dealer, _ = Dealer.objects.get_or_create(
        organization=org,
        code='DEAL01',
        defaults={
            'name': 'Test Dealer',
            'phone': '1234567890'
        }
    )
    print(f"✓ Dealer created: {dealer}")

    vehicle, _ = Vehicle.objects.get_or_create(
        organization=org,
        truck_number='CG15EA0001',
        defaults={
            'capacity': 10.0
        }
    )
    print(f"✓ Vehicle created: {vehicle}\n")

    # Test 1: Create Order using Model constructor + save() (with explicit org)
    print("Test 1: Creating Order with explicit organization...")
    try:
        order1 = Order(
            organization=org,
            dealer=dealer,
            vehicle=vehicle,
            depot=depot
        )
        order1.save()
        print(f"✓ Order created: {order1.order_number} with organization {order1.organization.name}")
        order1.delete()
    except Exception as e:
        print(f"✗ Order creation failed: {e}")
        import traceback
        traceback.print_exc()
        return False

    # Test 2: Create Order using objects.create() with explicit organization
    print("\nTest 2: Creating Order with objects.create() and explicit organization...")
    try:
        order2 = Order.objects.create(
            organization=org,
            dealer=dealer,
            vehicle=vehicle,
            depot=depot
        )
        print(f"✓ Order created: {order2.order_number} with organization {order2.organization.name}")
        order2.delete()
    except Exception as e:
        print(f"✗ Order creation failed: {e}")
        import traceback
        traceback.print_exc()
        return False

    # Test 3: Create Order WITHOUT explicit organization (should auto-assign from context)
    print("\nTest 3: Creating Order with auto-assignment from context...")
    try:
        order3 = Order(
            dealer=dealer,
            vehicle=vehicle,
            depot=depot
        )
        order3.save()
        assert order3.organization == org
        print(f"✓ Order created: {order3.order_number} with auto-assigned organization {order3.organization.name}")
        order3.delete()
    except Exception as e:
        print(f"✗ Order creation failed: {e}")
        import traceback
        traceback.print_exc()
        return False

    # Test 4: Simulate ViewSet create (passing organization as kwarg to save)
    print("\nTest 4: Creating Order like ViewSet (organization passed to save())...")
    try:
        order4 = Order(
            dealer=dealer,
            vehicle=vehicle,
            depot=depot
        )
        # This simulates what serializer.save(organization=org) does
        order4.organization = org
        order4.save()
        print(f"✓ Order created: {order4.order_number} with organization {order4.organization.name}")

        # Create order item
        item = OrderItem.objects.create(
            order=order4,
            product=product,
            quantity=10.5,
            unit_price=100.0
        )
        print(f"✓ OrderItem created with auto-assigned organization {item.organization.name}")

        order4.delete()
    except Exception as e:
        print(f"✗ Order creation failed: {e}")
        import traceback
        traceback.print_exc()
        return False

    # Clean up
    set_current_organization(None)

    print("\n✓ All tests passed! Order creation working correctly.")
    return True


if __name__ == '__main__':
    success = test_order_creation()
    sys.exit(0 if success else 1)
