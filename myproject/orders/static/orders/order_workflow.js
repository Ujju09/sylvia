

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
document.addEventListener('DOMContentLoaded', function() {
  const orderForm = document.getElementById('order-form');
  if (orderForm) {
    orderForm.addEventListener('submit', function(e) {
      const tableRows = document.querySelectorAll('#product-table tbody tr');
      if (tableRows.length === 0) {
        alert('Please add at least one product.');
        e.preventDefault();
        return;
      }
      // Remove any previous hidden inputs
      orderForm.querySelectorAll('input[name="product[]"], input[name="quantity[]"]').forEach(i => i.remove());
      tableRows.forEach(row => {
        const productId = row.querySelector('td[data-product-id]').getAttribute('data-product-id');
        const quantity = row.children[1].innerText;
        const productInput = document.createElement('input');
        productInput.type = 'hidden';
        productInput.name = 'product[]';
        productInput.value = productId;
        orderForm.appendChild(productInput);
        const quantityInput = document.createElement('input');
        quantityInput.type = 'hidden';
        quantityInput.name = 'quantity[]';
        quantityInput.value = quantity;
        orderForm.appendChild(quantityInput);
      });
    });
  }
});

