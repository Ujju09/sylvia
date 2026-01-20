#!/usr/bin/env python
"""
Test script to verify organization auto-assignment works correctly
"""
import os
import sys
import django

# Setup Django
sys.path.insert(0, os.path.dirname(__file__))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'myproject.settings')
django.setup()

from django.contrib.auth.models import User
from sylvia.models import Organization, UserProfile, Depot, Product, Dealer
from sylvia.middleware import set_current_organization


def test_organization_assignment():
    """Test that organization is auto-assigned from context"""

    # Get or create test organization
    org, _ = Organization.objects.get_or_create(
        slug='test-org',
        defaults={'name': 'Test Organization', 'is_active': True}
    )

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

    # Set organization context (simulating middleware)
    set_current_organization(org)

    print("✓ Organization context set")

    # Test 1: Create Depot without explicitly setting organization
    try:
        depot = Depot(
            name='Test Depot',
            code='TD001',
            city='Test City',
            state='Test State'
        )
        depot.save()
        assert depot.organization == org
        print(f"✓ Depot created with auto-assigned organization: {depot.organization.name}")
        depot.delete()
    except Exception as e:
        print(f"✗ Depot creation failed: {e}")
        return False

    # Test 2: Create Product without explicitly setting organization
    try:
        product = Product(
            name='Test Product',
            code='TP001',
            unit='MT'
        )
        product.save()
        assert product.organization == org
        print(f"✓ Product created with auto-assigned organization: {product.organization.name}")
        product.delete()
    except Exception as e:
        print(f"✗ Product creation failed: {e}")
        return False

    # Test 3: Create Dealer without explicitly setting organization
    try:
        dealer = Dealer(
            name='Test Dealer',
            code='TDL001',
            phone='1234567890'
        )
        dealer.save()
        assert dealer.organization == org
        print(f"✓ Dealer created with auto-assigned organization: {dealer.organization.name}")
        dealer.delete()
    except Exception as e:
        print(f"✗ Dealer creation failed: {e}")
        return False

    # Clean up
    set_current_organization(None)

    print("\n✓ All tests passed! Organization auto-assignment working correctly.")
    return True


if __name__ == '__main__':
    success = test_organization_assignment()
    sys.exit(0 if success else 1)
