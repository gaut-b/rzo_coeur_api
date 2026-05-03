/**
 * cart_attrib_confirm_delete.js
 *
 * On the Cart change form, intercept form submission when all article
 * checkboxes are unchecked. Prompt the user for confirmation before allowing
 * the server to delete the empty cart.
 *
 * Only activates when at least one `input[name="articles"]` checkbox exists
 * on the page (i.e. on the cart edit page for non-collected carts).
 */
(function () {
  'use strict';

  document.addEventListener('DOMContentLoaded', function () {
    var checkboxes = document.querySelectorAll('input[name="articles"]');
    if (checkboxes.length === 0) {
      return;
    }

    var form = document.querySelector('#cart_form');
    if (!form) {
      return;
    }

    form.addEventListener('submit', function (event) {
      var anyChecked = Array.prototype.some.call(
        document.querySelectorAll('input[name="articles"]'),
        function (cb) {
          return cb.checked;
        },
      );

      if (!anyChecked) {
        var confirmed = window.confirm(
          'Tous les articles ont été retirés du panier. Supprimer ce panier ?',
        );
        if (!confirmed) {
          event.preventDefault();
        }
      }
    });
  });
})();
