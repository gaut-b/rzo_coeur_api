/**
 * Address autocomplete with Géoplateforme API for Django admin
 * Includes an interactive Leaflet.js map to visualize the position
 */

(function () {
  'use strict';

  // Configuration
  const DEBOUNCE_DELAY = 400; // ms
  const MIN_QUERY_LENGTH = 3;
  const GEOPLATEFORME_API = 'https://data.geopf.fr/geocodage/search';

  // Global variables
  let debounceTimer = null;
  let map = null;
  let marker = null;

  // Initialization function
  function initAddressAutocomplete() {
    // Find the address input field (created by our custom form)
    const addressInput = document.getElementById('id_address');
    if (!addressInput) return;

    // Create suggestions container
    const suggestionsContainer = createSuggestionsContainer(addressInput);

    // Create map container
    const mapContainer = createMapContainer(addressInput);

    // Event listeners
    addressInput.addEventListener('input', handleAddressInput);
    addressInput.addEventListener('focus', handleAddressInput);
    document.addEventListener('click', handleOutsideClick);

    // Initialize map if coordinates already exist
    initializeMap();
  }

  function createSuggestionsContainer(inputElement) {
    const container = document.createElement('div');
    container.id = 'address-suggestions';
    container.className = 'address-suggestions';

    // Insert after the input element
    inputElement.parentNode.insertBefore(container, inputElement.nextSibling);

    // Make sure parent has position context
    const parent = inputElement.parentNode;
    if (parent && window.getComputedStyle(parent).position === 'static') {
      parent.style.position = 'relative';
    }

    return container;
  }

  function createMapContainer(inputElement) {
    const latInput = document.getElementById('id_latitude');
    const lonInput = document.getElementById('id_longitude');

    // Find the right location for the map (after coordinate fields)
    const container = document.createElement('div');
    container.id = 'shop-map-container';
    container.innerHTML = `
            <div id="shop-map" style="height: 300px; width: 100%; margin-top: 10px; border: 1px solid #ccc; border-radius: 4px;"></div>
            <p class="help" style="margin-top: 5px; font-size: 12px; color: #666;">
                The map will be displayed once an address has been selected.
            </p>
        `;

    // Insert after longitude input
    if (lonInput && lonInput.parentNode && lonInput.parentNode.parentNode) {
      lonInput.parentNode.parentNode.appendChild(container);
    }

    return container;
  }

  function handleAddressInput(e) {
    const query = e.target.value.trim();

    // Clear previous timer
    if (debounceTimer) {
      clearTimeout(debounceTimer);
    }

    // If query is too short, hide suggestions
    if (query.length < MIN_QUERY_LENGTH) {
      hideSuggestions();
      return;
    }

    // Debounce: wait for user to stop typing
    debounceTimer = setTimeout(() => {
      fetchAddressSuggestions(query);
    }, DEBOUNCE_DELAY);
  }

  function fetchAddressSuggestions(query) {
    const params = new URLSearchParams({
      q: query,
      index: 'address',
      autocomplete: '1',
      limit: 10,
    });

    // Show loading indicator
    showLoadingIndicator();

    fetch(`${GEOPLATEFORME_API}?${params}`)
      .then((response) => {
        if (!response.ok) {
          throw new Error('Error during address search');
        }
        return response.json();
      })
      .then((data) => {
        // Transform Géoplateforme response to our format
        const results = (data.features || []).map((feature) => {
          const props = feature.properties || {};
          const coords = feature.geometry?.coordinates || [];

          // Handle different address types (housenumber vs locality)
          let streetNumber = props.housenumber || '';
          let streetName = props.street || '';

          // For locality type, try to extract number from name
          if (props.type === 'locality' && props.name) {
            const nameMatch = props.name.match(/^(\d+)\s+(.+)$/);
            if (nameMatch) {
              streetNumber = nameMatch[1];
              streetName = nameMatch[2];
            } else {
              // No number in name, use locality or name as street
              streetName = props.locality || props.name;
            }
          }

          return {
            label: props.label || '',
            street_number: streetNumber,
            street_name: streetName,
            city: props.city || '',
            postal_code: props.postcode || '',
            latitude: coords[1] || '',
            longitude: coords[0] || '',
            score: props.score || 0,
          };
        });
        displaySuggestions(results);
      })
      .catch((error) => {
        console.error('Erreur:', error);
        displayError(error.message);
      });
  }

  function showLoadingIndicator() {
    const container = document.getElementById('address-suggestions');
    const addressInput = document.getElementById('id_address');

    container.innerHTML =
      '<div class="suggestion-item loading">Searching...</div>';

    // Position the container using fixed positioning
    positionSuggestions(addressInput, container);

    container.style.display = 'block';
  }

  function displaySuggestions(results) {
    const container = document.getElementById('address-suggestions');
    const addressInput = document.getElementById('id_address');

    if (results.length === 0) {
      container.innerHTML =
        '<div class="suggestion-item no-results">No address found</div>';

      // Position the container
      positionSuggestions(addressInput, container);

      container.style.display = 'block';
      return;
    }

    container.innerHTML = '';
    results.forEach((result) => {
      const item = document.createElement('div');
      item.className = 'suggestion-item';
      item.textContent = result.label;
      item.dataset.result = JSON.stringify(result);

      item.addEventListener('click', () => selectAddress(result));

      container.appendChild(item);
    });

    // Position the container
    positionSuggestions(addressInput, container);

    container.style.display = 'block';
  }

  function positionSuggestions(inputElement, container) {
    const rect = inputElement.getBoundingClientRect();
    container.style.top = `${rect.bottom + 2}px`;
    container.style.left = `${rect.left}px`;
    container.style.width = `${rect.width}px`;
  }

  function displayError(message) {
    const container = document.getElementById('address-suggestions');
    container.innerHTML = `<div class="suggestion-item error">${message}</div>`;
    container.style.display = 'block';
  }

  function selectAddress(result) {
    // Fill form fields
    document.getElementById('id_address').value = result.label;
    document.getElementById('id_street_number').value =
      result.street_number || '';
    document.getElementById('id_street_name').value = result.street_name || '';
    document.getElementById('id_city').value = result.city || '';
    document.getElementById('id_postal_code').value = result.postal_code || '';
    document.getElementById('id_latitude').value = result.latitude || '';
    document.getElementById('id_longitude').value = result.longitude || '';

    // Hide suggestions
    hideSuggestions();

    // Update map
    updateMap(result.latitude, result.longitude, result.label);
  }

  function hideSuggestions() {
    const container = document.getElementById('address-suggestions');
    container.style.display = 'none';
    container.innerHTML = '';
  }

  function handleOutsideClick(e) {
    const suggestionsContainer = document.getElementById('address-suggestions');
    const addressInput = document.getElementById('id_address');

    if (
      suggestionsContainer &&
      !suggestionsContainer.contains(e.target) &&
      e.target !== addressInput
    ) {
      hideSuggestions();
    }
  }

  function initializeMap() {
    const latInput = document.getElementById('id_latitude');
    const lonInput = document.getElementById('id_longitude');

    if (!latInput || !lonInput) return;

    const lat = parseFloat(latInput.value);
    const lon = parseFloat(lonInput.value);

    if (!isNaN(lat) && !isNaN(lon)) {
      const label = document.getElementById('id_address')?.value || '';
      updateMap(lat, lon, label);
    }
  }

  function updateMap(latitude, longitude, label) {
    const mapElement = document.getElementById('shop-map');
    if (!mapElement) return;

    // Create map if it doesn't exist yet
    if (!map) {
      map = L.map('shop-map').setView([latitude, longitude], 15);

      // Add OpenStreetMap layer
      L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
        attribution:
          '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>',
        maxZoom: 19,
      }).addTo(map);

      // Create marker
      marker = L.marker([latitude, longitude]).addTo(map);
      if (label) {
        marker.bindPopup(label).openPopup();
      }
    } else {
      // Update position
      map.setView([latitude, longitude], 15);
      marker.setLatLng([latitude, longitude]);
      if (label) {
        marker.bindPopup(label).openPopup();
      }
    }
  }

  // Initialize on page load
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initAddressAutocomplete);
  } else {
    initAddressAutocomplete();
  }
})();
