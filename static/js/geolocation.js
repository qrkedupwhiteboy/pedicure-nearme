// Get location input element
const locationInput = document.getElementById('location-input');
const suggestionsContainer = document.createElement('div');
suggestionsContainer.className = 'location-suggestions';
locationInput.parentNode.appendChild(suggestionsContainer);

// Function to get user's location using HTML5 Geolocation API
function getUserLocation() {
    if (navigator.geolocation) {
        locationInput.setAttribute('placeholder', 'Detecting your location...');
        
        navigator.geolocation.getCurrentPosition(
            async (position) => {
                try {
                    const response = await fetch(`/get_location?lat=${position.coords.latitude}&lon=${position.coords.longitude}`);
                    const data = await response.json();
                    
                    if (data.nearby_locations) {
                        showLocationSuggestions(data.nearby_locations);
                    }
                    
                    if (data.zipcode) {
                        locationInput.setAttribute('placeholder', `Locations near ${data.zipcode}`);
                    }
                } catch (error) {
                    console.log('Error getting location data:', error);
                    fallbackToIPLocation();
                }
            },
            (error) => {
                console.log('Geolocation error:', error.message);
                fallbackToIPLocation();
            }
        );
    } else {
        fallbackToIPLocation();
    }
}

// Fallback to IP-based location using Geoapify
async function fallbackToIPLocation() {
    try {
        const response = await fetch('/get_ip_location');
        const data = await response.json();
        
        if (data.error) {
            throw new Error(data.error);
        }
        
        if (data.nearby_locations) {
            showLocationSuggestions(data.nearby_locations);
        }
        
        if (data.zipcode) {
            locationInput.setAttribute('placeholder', `Locations near ${data.zipcode}`);
        }
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
