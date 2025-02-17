// Get location input element
const locationInput = document.getElementById('location-input');
const suggestionsContainer = document.createElement('div');
suggestionsContainer.className = 'location-suggestions';
locationInput.parentNode.appendChild(suggestionsContainer);

// Function to display nearby locations
function showNearbyLocations(locations) {
    suggestionsContainer.innerHTML = locations.map(loc => `
        <div class="suggestion-item" data-value="${loc.zipcode}">
            <div class="suggestion-main">
                <span class="suggestion-city">${loc.city}</span>
                <span class="suggestion-detail">${loc.state} ${loc.zipcode}</span>
            </div>
            <span class="listing-count">${loc.listing_count} listings</span>
        </div>
    `).join('');

    // Add click handlers to suggestions
    document.querySelectorAll('.suggestion-item').forEach(item => {
        item.addEventListener('click', () => {
            const zipcode = item.dataset.value;
            locationInput.value = zipcode;
            suggestionsContainer.style.display = 'none';
            window.open(`/map/${zipcode}`, '_blank');
        });
    });
    
    suggestionsContainer.style.display = 'block';
}

// Get user's location using backend proxy for Geoapify
async function getUserLocation() {
    locationInput.setAttribute('placeholder', 'Detecting your location...');
    try {
        const response = await fetch('/get_geoapify_location');
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        const data = await response.json();
        
        console.log('Geoapify response:', data);
        
        if (data.error) {
            throw new Error(data.error);
        }

        if (data && data.location && data.location.latitude && data.location.longitude) {
            const nearbyResponse = await fetch(`/nearby_locations?lat=${data.location.latitude}&lon=${data.location.longitude}`);
            const nearbyData = await nearbyResponse.json();
            
            if (nearbyData.nearby_locations) {
                showNearbyLocations(nearbyData.nearby_locations);
            }
            
            // Store coordinates for later use
            localStorage.setItem('userLat', data.location.latitude);
            localStorage.setItem('userLon', data.location.longitude);
            
            const locationDisplay = (data.city && data.city.name) || 'your location';
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

// Get zipcode when input is focused
locationInput.addEventListener('focus', async () => {
    const lat = localStorage.getItem('userLat');
    const lon = localStorage.getItem('userLon');
    
    console.log('Stored coordinates:', {lat, lon});
    
    if (lat && lon) {
        const requestOptions = {
            method: 'GET',
            headers: {
                'Accept': 'application/json'
            }
        };

        fetch(`/get_zipcode?lat=${lat}&lon=${lon}`, requestOptions)
            .then(response => response.json())
            .then(data => {
                if (data.zipcode) {
                    const zipcodeDisplay = document.getElementById('current-zipcode');
                    zipcodeDisplay.style.display = 'block';
                    
                    localStorage.setItem('userZipcode', data.zipcode);
                    console.log('Stored zipcode:', data.zipcode);
                    
                    // Add click handler for current location button
                    document.getElementById('use-current-location').addEventListener('click', () => {
                        const zipcode = localStorage.getItem('userZipcode');
                        if (zipcode) {
                            window.open(`/map/${zipcode}`, '_blank');
                        } else {
                            const lat = localStorage.getItem('userLat');
                            const lon = localStorage.getItem('userLon');
                            if (lat && lon) {
                                window.location.href = `/search?lat=${lat}&lon=${lon}`;
                            }
                        }
                    });
                } else {
                    console.warn('No zipcode in response:', data);
                }
            })
            .catch(error => {
                console.error('Error getting zipcode:', error);
            });
    }
    
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
        zipcodeDisplay.style.display = 'block';
    }
    getUserLocation();
});
