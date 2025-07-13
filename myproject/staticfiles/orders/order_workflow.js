

function addProductRow() {
  const productSelect = document.getElementById('product');
  const quantityInput = document.getElementById('quantity');
  const table = document.getElementById('product-table').getElementsByTagName('tbody')[0];
  const product = productSelect.options[productSelect.selectedIndex].text;
  const productId = productSelect.value;
  const quantity = quantityInput.value;
  if (!quantity || quantity <= 0 || !productId) return;
  const row = table.insertRow();
  row.innerHTML = `<td data-product-id='${productId}'>${product}</td><td>${quantity}</td><td><button type='button' class='btn btn-sm btn-danger' onclick='this.closest(\"tr\").remove()'>Remove</button></td>`;
  quantityInput.value = '';
  productSelect.selectedIndex = 0;
}




// Handle order form submission for products
// Updated validation for new product UI
document.addEventListener('DOMContentLoaded', function() {
  const orderForm = document.getElementById('order-form');
  if (orderForm) {
    orderForm.addEventListener('submit', function(e) {
      // Find all product quantity inputs
      const productInputs = orderForm.querySelectorAll('input[name^="product_"]');
      let valid = false;
      productInputs.forEach(function(input) {
        const val = parseFloat(input.value);
        if (!isNaN(val) && val > 0) {
          valid = true;
        }
      });
      if (!valid) {
        alert('Please add at least one product quantity before submitting.');
        e.preventDefault();
        return false;
      }
    });
  }
});

