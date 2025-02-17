// Get location input element
const locationInput = document.getElementById('location-input');
const suggestionsContainer = document.createElement('div');
suggestionsContainer.className = 'location-suggestions';
locationInput.parentNode.appendChild(suggestionsContainer);

// Get user's location using backend proxy for Geoapify
async function getUserLocation() {
    locationInput.setAttribute('placeholder', 'Detecting your location...');
    try {
        const response = await fetch('/get_geoapify_location');
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        const data = await response.json();
        
        // Log the full response for debugging
        console.log('Geoapify response:', data);
        
        if (data.error) {
            throw new Error(data.error);
        }

        // Check for location data in the correct structure
        if (data && data.location && data.location.latitude && data.location.longitude) {
            const nearbyResponse = await fetch(`/nearby_locations?lat=${data.location.latitude}&lon=${data.location.longitude}`);
            const nearbyData = await nearbyResponse.json();
            
            if (nearbyData.nearby_locations) {
                showLocationSuggestions(nearbyData.nearby_locations);
            }
            
            // Use postcode if available, otherwise use city name
            // Display and store the zipcode if available
            const zipcodeDisplay = document.getElementById('current-zipcode');
            if (data.postcode) {
                const zipcode = data.postcode;
                zipcodeDisplay.textContent = `Your current ZIP code: ${zipcode}`;
                zipcodeDisplay.style.display = 'block';
                
                // Store zipcode in localStorage
                localStorage.setItem('userZipcode', zipcode);
                console.log('Stored zipcode:', zipcode);
            } else {
                console.warn('No zipcode found in location data');
                localStorage.removeItem('userZipcode');
            }
            
            // Use postcode if available, otherwise use city name
            const locationDisplay = data.postcode || 
                                 (data.city && data.city.name) || 
                                 'your location';
            
            locationInput.setAttribute('placeholder', `Locations near ${locationDisplay}`);
        } else {
            console.log('Invalid location data structure:', data);
            throw new Error('Could not determine location');
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

// Function to get stored zipcode
function getStoredZipcode() {
    const zipcode = localStorage.getItem('userZipcode');
    console.log('Retrieved stored zipcode:', zipcode);
    return zipcode;
}

// Initialize location detection when page loads
document.addEventListener('DOMContentLoaded', () => {
    const storedZipcode = getStoredZipcode();
    if (storedZipcode) {
        const zipcodeDisplay = document.getElementById('current-zipcode');
        zipcodeDisplay.textContent = `Your current ZIP code: ${storedZipcode}`;
        zipcodeDisplay.style.display = 'block';
    }
    getUserLocation();
});
