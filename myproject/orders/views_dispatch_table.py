import logging
import json
import base64
from decimal import Decimal, InvalidOperation
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.db import transaction
from django.contrib import messages
from sylvia.models import Vehicle, Dealer, Product, Order, OrderItem, Depot
from datetime import datetime
from django.utils import timezone
import anthropic
from django.conf import settings

logger = logging.getLogger(__name__)

# Configuration for anthropic client
try:
    claude_client = anthropic.Anthropic(api_key=getattr(settings, 'ANTHROPIC_API_KEY', ''))
except Exception as e:
    logger.error(f"Failed to initialize Anthropic client: {e}")
    claude_client = None

@login_required
def dispatch_table_upload(request):
    """View for uploading and processing dispatch table images"""
    context = {
        'title': 'Dispatch Table Image Processor',
        'form_action': 'process_dispatch_image'
    }
    return render(request, 'orders/dispatch_table_upload.html', context)

@login_required
@csrf_exempt
def process_dispatch_image(request):
    """Process the uploaded dispatch table image using Claude vision API"""
    if request.method != 'POST':
        return JsonResponse({'error': 'Only POST method allowed'}, status=405)
    
    if not claude_client:
        return JsonResponse({
            'error': 'Anthropic API not configured. Please check ANTHROPIC_API_KEY setting.'
        }, status=500)
    
    try:
        # Get uploaded image
        image_file = request.FILES.get('dispatch_image')
        if not image_file:
            return JsonResponse({'error': 'No image file provided'}, status=400)
        
        # Validate image type
        if not image_file.content_type.startswith('image/'):
            return JsonResponse({'error': 'Please upload a valid image file'}, status=400)
        
        # Convert image to base64
        image_data = image_file.read()
        image_base64 = base64.b64encode(image_data).decode('utf-8')
        
        # Prepare Claude vision prompt with product and depot mapping
        prompt = """
        Analyze this dispatch table image and extract the following information for each row:
        
        FLEXIBLE COLUMN MAPPING - Look for these data types regardless of exact header names:
        1. Depot/Plant/Location Name → Depot (map using depot correlation table below)
        2. Date/Invoice Date/Plant Date/Dispatch Date → Order Date (CRITICAL: see date parsing rules below)
        3. Transporter/Carrier/Owner → Vehicle Owner
        4. Vehicle/Truck Number/Registration → Truck Number
        5. Quantity/Dispatch Qty/Amount → Quantity (extract numeric value)
        6. Product/Material/Item Description → Product Name (map using product correlation table below)
        7. Party/Dealer/Customer Name → Dealer Name (if empty, use "Anonymous")
        
        CRITICAL DATE PARSING RULES:
        - Parse dates in ANY format (DD/MM/YYYY, DD-MM-YYYY, DD.MM.YYYY, etc.)
        - Convert ALL dates to YYYY-MM-DD format
        - Examples: "01/08/2025" → "2025-08-01", "30.7.25" → "2025-07-30"
        
        IMPORTANT - Be flexible with column headers. The actual headers may vary but look for the data types described above.
        
        IMPORTANT - Depot Name Mapping:
        Use this correlation table to map depot descriptions to standard depot names:
        - "JH NAGARUNTARI BC TR [VD]" → "Nagar Untari Depot"
        - "JH CHHATTARPUR BC TR [VD]" → "Chhatarpur Depot"
        
        If the depot description doesn't match exactly, find the closest match from the correlation table.
        
        IMPORTANT - Product Name Mapping:
        Use this correlation table to map product descriptions to standard product names:
        - "MAGNA TR CC LPP 50KG" → "Magna"
        - "POWERMAX TR PPC PP 50KG" → "Powermax"
        - "POWERMAX TR PPC LPP 50KG" → "Powermax―LPP"
        - "JUNGRODHAK TR PPC PP 50KG" → "Jungrodhak"
        - "JUNGRODHAK TR PPC LPP 50KG" → "Jungrodhak―LPP"
        - "Marble TR PSC LPP 50 KG" → "Marble"
        - "Roofon Plus CC LPP 50KG" → "Roofon Plus"
        
        If the product description doesn't match exactly, find the closest match from the correlation table.
        
        CRITICAL: Return ONLY a valid JSON array with objects containing these exact fields:
        - depot_name (use mapped name from depot correlation table)
        - order_date
        - vehicle_owner
        - truck_number
        - quantity
        - product_name (use mapped name from product correlation table)
        - dealer_name
        
        Important rules:
        - If any field is missing or unclear, use reasonable defaults
        - For quantities, extract only the numeric value (e.g., "25.5 MT" → "25.5")
        - For dates, STRICTLY follow the date parsing rules above - ensure YYYY-MM-DD format 
        - For truck numbers, clean format (e.g., "CG 15 EA 0464" → "CG15EA0464")
        - If dealer is empty, use "Anonymous"
        - ALWAYS use the mapped depot names from the depot correlation table
        - ALWAYS use the mapped product names from the product correlation table
        - Do NOT include any explanatory text, only return the JSON array
        - If you cannot parse the table, return an empty array: []
        
        Example output format:
        [
          {
            "depot_name": "Nagar Untari Depot",
            "order_date": "2024-01-15",
            "vehicle_owner": "ABC Transport",
            "truck_number": "CG15EA0464",
            "quantity": "25.5",
            "product_name": "Magna",
            "dealer_name": "XYZ Dealers"
          }
        ]
        """
        
        # Call Claude vision API
        try:
            message = claude_client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=6000,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "image",
                                "source": {
                                    "type": "base64",
                                    "media_type": image_file.content_type,
                                    "data": image_base64
                                }
                            },
                            {
                                "type": "text",
                                "text": prompt
                            }
                        ]
                    }
                ]
            )
            
            # Extract response text
            response_text = message.content[0].text.strip()
            
            # Log the raw response for debugging
            
            # Parse JSON response
            try:
                extracted_data = json.loads(response_text)
            except json.JSONDecodeError as e:
                logger.error(f"JSON decode error: {e}")
                # Try to extract JSON from response if it's wrapped in text
                start_idx = response_text.find('[')
                end_idx = response_text.rfind(']') + 1
                if start_idx >= 0 and end_idx > start_idx:
                    json_text = response_text[start_idx:end_idx]
                    try:
                        extracted_data = json.loads(json_text)
                    except json.JSONDecodeError as e2:
                        logger.error(f"Failed to parse extracted JSON: {e2}")
                        return JsonResponse({
                            'error': 'Could not parse response from image analysis. Please try again or check if the image is clear.',
                            'debug_info': f'Response preview: {response_text[:200]}...'
                        }, status=400)
                else:
                    logger.error(f"No JSON array found in response: {response_text}")
                    return JsonResponse({
                        'error': 'No valid data structure found in image analysis response. Please ensure the image contains a clear dispatch table.',
                        'debug_info': f'Response preview: {response_text[:200]}...'
                    }, status=400)
            
            if not isinstance(extracted_data, list):
                logger.error(f"Response is not a list: {type(extracted_data)}")
                return JsonResponse({
                    'error': 'Invalid data format from image analysis. Expected a list of dispatch entries.',
                    'debug_info': f'Received: {type(extracted_data).__name__}'
                }, status=400)
            
            # Validate and process the extracted data
            processed_data = validate_and_process_data(extracted_data)
            
            # Store in session for confirmation step
            request.session['extracted_dispatch_data'] = processed_data
            
            return JsonResponse({
                'success': True,
                'data': processed_data,
                'message': f'Successfully extracted {len(processed_data["rows"])} dispatch entries'
            })
            
        except anthropic.APIError as e:
            logger.error(f"Anthropic API error: {e}")
            return JsonResponse({'error': f'API error: {str(e)}'}, status=500)
        except Exception as e:
            logger.error(f"Error processing image with Claude: {e}")
            return JsonResponse({'error': f'Image processing failed: {str(e)}'}, status=500)
    
    except Exception as e:
        logger.error(f"Error in process_dispatch_image: {e}")
        return JsonResponse({'error': f'Processing failed: {str(e)}'}, status=500)

def validate_and_process_data(raw_data):
    """Validate extracted data against database and prepare for confirmation"""
    processed_rows = []
    validation_summary = {
        'total_rows': len(raw_data),
        'valid_rows': 0,
        'warnings': [],
        'missing_entities': {
            'depots': [],
            'vehicles': [],
            'products': [],
            'dealers': []
        }
    }
    
    # Get existing entities for validation
    existing_depots = {depot.name.lower(): depot for depot in Depot.objects.filter(is_active=True)}
    existing_vehicles = {vehicle.truck_number.upper(): vehicle for vehicle in Vehicle.objects.filter(is_active=True)}
    existing_products = {product.name.lower(): product for product in Product.objects.filter(is_active=True)}
    existing_dealers = {dealer.name.lower(): dealer for dealer in Dealer.objects.filter(is_active=True)}
    
    for i, row in enumerate(raw_data):
        processed_row = {
            'row_number': i + 1,
            'depot_name': row.get('depot_name', '').strip(),
            'order_date': row.get('order_date', ''),
            'vehicle_owner': row.get('vehicle_owner', '').strip(),
            'truck_number': clean_truck_number(row.get('truck_number', '')),
            'quantity': parse_quantity(row.get('quantity', '0')),
            'product_name': row.get('product_name', '').strip(),
            'dealer_name': row.get('dealer_name', 'Anonymous').strip() or 'Anonymous',
            'validation_status': 'valid',
            'warnings': [],
            'entities_found': {},
            'entities_to_create': {}
        }
        
        # Validate depot
        depot_key = processed_row['depot_name'].lower()
        if depot_key in existing_depots:
            processed_row['entities_found']['depot'] = {
                'id': existing_depots[depot_key].id,
                'name': existing_depots[depot_key].name
            }
        else:
            if processed_row['depot_name'] not in validation_summary['missing_entities']['depots']:
                validation_summary['missing_entities']['depots'].append(processed_row['depot_name'])
            processed_row['entities_to_create']['depot'] = True
            processed_row['warnings'].append('Depot will be created')
        
        # Validate vehicle
        truck_key = processed_row['truck_number'].upper()
        if truck_key in existing_vehicles:
            processed_row['entities_found']['vehicle'] = {
                'id': existing_vehicles[truck_key].id,
                'truck_number': existing_vehicles[truck_key].truck_number
            }
        else:
            if processed_row['truck_number'] not in validation_summary['missing_entities']['vehicles']:
                validation_summary['missing_entities']['vehicles'].append(processed_row['truck_number'])
            processed_row['entities_to_create']['vehicle'] = True
            processed_row['warnings'].append('Vehicle will be created')
        
        # Validate product with enhanced matching
        product_key = processed_row['product_name'].lower()
        product_found = False
        
        # First try exact match
        if product_key in existing_products:
            processed_row['entities_found']['product'] = {
                'id': existing_products[product_key].id,
                'name': existing_products[product_key].name
            }
            product_found = True
        else:
            # Try fuzzy matching
            for existing_product_key, product in existing_products.items():
                if existing_product_key in product_key or product_key in existing_product_key:
                    processed_row['entities_found']['product'] = {
                        'id': product.id,
                        'name': product.name
                    }
                    product_found = True
                    break
        
        if not product_found:
            if processed_row['product_name'] not in validation_summary['missing_entities']['products']:
                validation_summary['missing_entities']['products'].append(processed_row['product_name'])
            processed_row['entities_to_create']['product'] = True
            processed_row['warnings'].append('Product will be created')
        
        # Validate dealer (always check Anonymous dealer)
        dealer_key = processed_row['dealer_name'].lower()
        if dealer_key == 'anonymous':
            # Get or prepare Anonymous dealer
            anonymous_dealer = existing_dealers.get('anonymous')
            if anonymous_dealer:
                processed_row['entities_found']['dealer'] = {
                    'id': anonymous_dealer.id,
                    'name': anonymous_dealer.name
                }
            else:
                if 'Anonymous' not in validation_summary['missing_entities']['dealers']:
                    validation_summary['missing_entities']['dealers'].append('Anonymous')
                processed_row['entities_to_create']['dealer'] = True
                processed_row['warnings'].append('Anonymous dealer will be created')
        else:
            if dealer_key in existing_dealers:
                processed_row['entities_found']['dealer'] = {
                    'id': existing_dealers[dealer_key].id,
                    'name': existing_dealers[dealer_key].name
                }
            else:
                if processed_row['dealer_name'] not in validation_summary['missing_entities']['dealers']:
                    validation_summary['missing_entities']['dealers'].append(processed_row['dealer_name'])
                processed_row['entities_to_create']['dealer'] = True
                processed_row['warnings'].append('Dealer will be created')
        
        # Validate date
        try:
            datetime.strptime(processed_row['order_date'], '%Y-%m-%d')
        except ValueError:
            processed_row['warnings'].append('Invalid date format - will use today')
            processed_row['order_date'] = timezone.now().date().strftime('%Y-%m-%d')
        
        # Validate quantity
        if processed_row['quantity'] <= 0:
            processed_row['validation_status'] = 'invalid'
            processed_row['warnings'].append('Invalid quantity')
        
        if processed_row['validation_status'] == 'valid':
            validation_summary['valid_rows'] += 1
        
        processed_rows.append(processed_row)
    
    return {
        'rows': processed_rows,
        'summary': validation_summary,
        'missing_entities': validation_summary['missing_entities']
    }

def clean_truck_number(truck_number):
    """Clean and format truck number"""
    if not truck_number:
        return ''
    
    # Remove spaces and convert to uppercase
    cleaned = ''.join(truck_number.split()).upper()
    
    # Basic validation for Indian truck number format
    if len(cleaned) >= 8:
        return cleaned
    
    return truck_number.strip()

def parse_quantity(quantity_str):
    """Parse quantity from string, extracting numeric value"""
    if not quantity_str:
        return 0
    
    # Extract numeric part
    import re
    numeric_match = re.search(r'(\d+\.?\d*)', str(quantity_str))
    if numeric_match:
        try:
            return float(numeric_match.group(1))
        except ValueError:
            return 0
    
    return 0

@login_required
def confirm_dispatch_data(request):
    """Display confirmation page with validation results"""
    extracted_data = request.session.get('extracted_dispatch_data')
    
    if not extracted_data:
        messages.error(request, 'No dispatch data found. Please upload an image first.')
        return redirect('dispatch_table_upload')
    
    total_rows = len(extracted_data['rows'])
    valid_rows = extracted_data['summary']['valid_rows']
    invalid_rows = total_rows - valid_rows
    
    context = {
        'title': 'Confirm Dispatch Data',
        'data': extracted_data,
        'total_rows': total_rows,
        'valid_rows': valid_rows,
        'invalid_rows': invalid_rows,
        'missing_entities': extracted_data['missing_entities']
    }
    
    return render(request, 'orders/confirm_dispatch_data.html', context)

@login_required
def create_dispatch_orders(request):
    """Create orders from confirmed dispatch data"""
    if request.method != 'POST':
        return redirect('dispatch_table_upload')
    
    extracted_data = request.session.get('extracted_dispatch_data')
    if not extracted_data:
        messages.error(request, 'No dispatch data found. Please start over.')
        return redirect('dispatch_table_upload')
    
    try:
        with transaction.atomic():
            created_orders = []
            creation_log = []
            
            # Create missing entities first
            created_entities = create_missing_entities(extracted_data['missing_entities'], extracted_data)
            creation_log.extend(created_entities['log'])
            
            # Create orders
            for row in extracted_data['rows']:
                if row['validation_status'] != 'valid':
                    continue
                
                try:
                    # Get or create entities
                    depot = get_or_create_depot(row, created_entities)
                    vehicle = get_or_create_vehicle(row, created_entities)
                    product = get_or_create_product(row, created_entities)
                    dealer = get_or_create_dealer(row, created_entities)
                    
                    # Parse order date
                    order_date = datetime.strptime(row['order_date'], '%Y-%m-%d')
                    order_date = order_date.replace(hour=13, minute=0, second=0, microsecond=0)
                    order_date = timezone.make_aware(order_date)
                    
                    # Create order
                    order = Order.objects.create(
                        dealer=dealer,
                        vehicle=vehicle,
                        depot=depot,
                        order_date=order_date,
                        created_by=request.user
                    )
                    
                    # Create order item
                    OrderItem.objects.create(
                        order=order,
                        product=product,
                        quantity=Decimal(str(row['quantity']))
                    )
                    
                    created_orders.append(order)
                    creation_log.append(f"Created order {order.order_number} for {dealer.name}")
                    
                except Exception as e:
                    logger.error(f"Error creating order for row {row['row_number']}: {e}")
                    creation_log.append(f"Failed to create order for row {row['row_number']}: {str(e)}")
            
            # Clear session data
            if 'extracted_dispatch_data' in request.session:
                del request.session['extracted_dispatch_data']
            
            messages.success(request, f'Successfully created {len(created_orders)} orders from dispatch table.')
            
            context = {
                'title': 'Dispatch Orders Created',
                'created_orders': created_orders,
                'creation_log': creation_log,
                'total_created': len(created_orders)
            }
            
            return render(request, 'orders/dispatch_orders_created.html', context)
    
    except Exception as e:
        logger.error(f"Error creating dispatch orders: {e}")
        messages.error(request, f'Error creating orders: {str(e)}')
        return redirect('confirm_dispatch_data')

def create_missing_entities(missing_entities, processed_data):
    """Create missing depots, vehicles, products, and dealers"""
    created_entities = {
        'depots': {},
        'vehicles': {},
        'products': {},
        'dealers': {},
        'log': []
    }
    
    # Create depots
    for depot_name in missing_entities['depots']:
        depot_code = depot_name[:10].upper().replace(' ', '')
        depot = Depot.objects.create(
            name=depot_name,
            code=depot_code,
            city='Unknown',
            state='Unknown'
        )
        created_entities['depots'][depot_name.lower()] = depot
        created_entities['log'].append(f"Created depot: {depot_name}")
    
    # Create vehicles
    for truck_number in missing_entities['vehicles']:
        # Find the vehicle owner name from the processed data
        owner_name = 'Unknown'
        for row in processed_data.get('rows', []):
            if row.get('truck_number', '').upper() == truck_number.upper():
                owner_name = row.get('vehicle_owner', 'Unknown')
                break
        
        vehicle = Vehicle.objects.create(
            truck_number=truck_number,
            owner_name=owner_name,
            vehicle_type='TRUCK'
        )
        created_entities['vehicles'][truck_number.upper()] = vehicle
        created_entities['log'].append(f"Created vehicle: {truck_number} (Owner: {owner_name})")
    
    # Create products
    for product_name in missing_entities['products']:
        product_code = product_name[:20].upper().replace(' ', '')
        product = Product.objects.create(
            name=product_name,
            code=product_code,
            unit='MT'
        )
        created_entities['products'][product_name.lower()] = product
        created_entities['log'].append(f"Created product: {product_name}")
    
    # Create dealers
    for dealer_name in missing_entities['dealers']:
        if dealer_name.lower() == 'anonymous':
            dealer_code = 'ANON'
        else:
            dealer_code = dealer_name[:20].upper().replace(' ', '')
        
        dealer = Dealer.objects.create(
            name=dealer_name,
            code=dealer_code,
            phone='0000000000'
        )
        created_entities['dealers'][dealer_name.lower()] = dealer
        created_entities['log'].append(f"Created dealer: {dealer_name}")
    
    return created_entities

def get_or_create_depot(row, created_entities):
    """Get existing depot or return newly created one"""
    if 'depot' in row['entities_found']:
        # Return the actual model instance
        return Depot.objects.get(id=row['entities_found']['depot']['id'])
    
    depot_key = row['depot_name'].lower()
    return created_entities['depots'].get(depot_key)

def get_or_create_vehicle(row, created_entities):
    """Get existing vehicle or return newly created one"""
    if 'vehicle' in row['entities_found']:
        # Return the actual model instance
        return Vehicle.objects.get(id=row['entities_found']['vehicle']['id'])
    
    truck_key = row['truck_number'].upper()
    return created_entities['vehicles'].get(truck_key)

def get_or_create_product(row, created_entities):
    """Get existing product or return newly created one"""
    if 'product' in row['entities_found']:
        # Return the actual model instance
        return Product.objects.get(id=row['entities_found']['product']['id'])
    
    product_key = row['product_name'].lower()
    return created_entities['products'].get(product_key)

def get_or_create_dealer(row, created_entities):
    """Get existing dealer or return newly created one"""
    if 'dealer' in row['entities_found']:
        # Return the actual model instance
        return Dealer.objects.get(id=row['entities_found']['dealer']['id'])
    
    dealer_key = row['dealer_name'].lower()
    return created_entities['dealers'].get(dealer_key)