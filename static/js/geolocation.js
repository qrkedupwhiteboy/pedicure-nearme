// Get location input element
const locationInput = document.getElementById('location-input');
const suggestionsContainer = document.createElement('div');
suggestionsContainer.className = 'location-suggestions';
locationInput.parentNode.appendChild(suggestionsContainer);

// Get user's location using Geoapify IP Geolocation
async function getUserLocation() {
    locationInput.setAttribute('placeholder', 'Detecting your location...');
    try {
        const response = await fetch(`https://api.geoapify.com/v1/ipinfo?apiKey=${GEOAPIFY_API_KEY}`);
        const data = await response.json();
        
        if (!response.ok) {
            throw new Error('Failed to get location data');
        }

        const zipCode = data.postal.code;
        const city = data.city.name;
        const state = data.state.code;

        // Get nearby locations from our backend
        const nearbyResponse = await fetch(`/nearby_locations?lat=${data.location.latitude}&lon=${data.location.longitude}`);
        const nearbyData = await nearbyResponse.json();
        
        if (nearbyData.nearby_locations) {
            showLocationSuggestions(nearbyData.nearby_locations);
        }
        
        locationInput.setAttribute('placeholder', `Locations near ${zipCode}`);
    } catch (error) {
        console.log('Location detection unavailable:', error);
        locationInput.setAttribute('placeholder', 'Enter your ZIP code or city');
    }
}

function showLocationSuggestions(locations) {
    suggestionsContainer.innerHTML = locations.map(loc => `
        <div class="suggestion-item" data-value="${loc.zipcode}">
            <span class="suggestion-city">${loc.city}</span>
            <span class="suggestion-detail">${loc.state} ${loc.zipcode}</span>
        </div>
    `).join('');

    // Add click handlers to suggestions
    document.querySelectorAll('.suggestion-item').forEach(item => {
        item.addEventListener('click', () => {
            locationInput.value = item.dataset.value;
            suggestionsContainer.style.display = 'none';
        });
    });
}

// Show suggestions when input is focused
locationInput.addEventListener('focus', () => {
    if (suggestionsContainer.children.length > 0) {
        suggestionsContainer.style.display = 'block';
    }
});

// Hide suggestions when clicking outside
document.addEventListener('click', (e) => {
    if (!locationInput.contains(e.target) && !suggestionsContainer.contains(e.target)) {
        suggestionsContainer.style.display = 'none';
    }
});

// Initialize location detection when page loads
document.addEventListener('DOMContentLoaded', getUserLocation);
