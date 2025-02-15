let map;
let markers = [];

function initMap() {
    map = L.map('map').setView([39.8283, -98.5795], 4);
    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
        attribution: '© OpenStreetMap contributors'
    }).addTo(map);
}

function clearMarkers() {
    markers.forEach(marker => marker.remove());
    markers = [];
}

function addMarker(lat, lng, popupContent) {
    const marker = L.marker([lat, lng])
        .bindPopup(popupContent)
        .addTo(map);
    markers.push(marker);
}

function getCurrentLocation() {
    if (navigator.geolocation) {
        navigator.geolocation.getCurrentPosition(
            function(position) {
                const latitude = position.coords.latitude;
                const longitude = position.coords.longitude;
                
                fetch(`https://nominatim.openstreetmap.org/reverse?format=json&lat=${latitude}&lon=${longitude}`)
                    .then(response => response.json())
                    .then(data => {
                        const locationInput = document.getElementById('location-input');
                        // Try to get ZIP code first
                        const postcode = data.address.postcode;
                        if (postcode) {
                            locationInput.value = postcode;
                        } else {
                            // Fall back to city name
                            const city = data.address.city || data.address.town || data.address.village;
                            if (city) {
                                locationInput.value = city;
                            } else {
                                locationInput.value = data.display_name;
                            }
                        }
                    })
                    .catch(error => {
                        console.error('Error getting location name:', error);
                        alert('Unable to get your location name. Please enter it manually.');
                    });
                
                // Center map on user location
                map.setView([latitude, longitude], 12);
                clearMarkers();
                addMarker(latitude, longitude, 'Your Location');
            },
            function(error) {
                console.error('Error getting location:', error);
                alert('Unable to get your location. Please enable location services or enter your location manually.');
            }
        );
    } else {
        alert('Geolocation is not supported by your browser. Please enter your location manually.');
    }
}

function searchLocation() {
    const locationInput = document.getElementById('location-input');
    const location = locationInput.value.trim();
    
    if (!location) return;

    // If it's a ZIP code
    if (location.match(/^\d{5}$/)) {
        fetch(`/search?location=${location}&format=json`)
            .then(response => response.json())
            .then(data => {
                clearMarkers();
                data.listings.forEach(listing => {
                    if (listing.latitude && listing.longitude) {
                        const popupContent = `
                            <div class="map-popup">
                                <h3>${listing.business_name}</h3>
                                <p>Rating: ${listing.rating} ⭐ (${listing.reviews} reviews)</p>
                                <p>${listing.address}</p>
                                ${listing.phone ? `<p>📞 ${listing.phone}</p>` : ''}
                                <a href="/listing/${listing.id}" class="view-details">View Details</a>
                            </div>
                        `;
                        addMarker(listing.latitude, listing.longitude, popupContent);
                    }
                });
                
                // Center map on first result
                if (data.listings.length > 0 && data.listings[0].latitude) {
                    map.setView([data.listings[0].latitude, data.listings[0].longitude], 12);
                }
            })
            .catch(error => {
                console.error('Error searching locations:', error);
                alert('Error searching for locations. Please try again.');
            });
    }
}

// Initialize map when DOM is loaded
document.addEventListener('DOMContentLoaded', function() {
    initMap();

// Add view toggle functionality
document.addEventListener('DOMContentLoaded', function() {
    const viewButtons = document.querySelectorAll('.view-button');
    const mapContainer = document.querySelector('.map-container');
    const listingsGrid = document.querySelector('.listings-grid');
    const mapFrame = document.querySelector('.map-frame');

    // Set initial state
    mapContainer.style.display = 'none';
    listingsGrid.style.display = 'grid';

    viewButtons.forEach(button => {
        button.addEventListener('click', function() {
            // Remove active class from all buttons
            viewButtons.forEach(b => b.classList.remove('active'));
            // Add active class to clicked button
            this.classList.add('active');
            
            if (this.dataset.view === 'map') {
                mapContainer.style.display = 'block';
                listingsGrid.style.display = 'none';
                // Force map reload
                if (mapFrame) {
                    mapFrame.src = mapFrame.src;
                }
            } else {
                mapContainer.style.display = 'none';
                listingsGrid.style.display = 'grid';
            }
        });
    });
});
