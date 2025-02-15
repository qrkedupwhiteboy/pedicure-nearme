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

// Add view toggle functionality
document.addEventListener('DOMContentLoaded', function() {
    const viewButtons = document.querySelectorAll('.view-button');
    const mapContainer = document.querySelector('.map-container');
    const listingsGrid = document.querySelector('.listings-grid');
    const mapFrame = document.querySelector('.map-frame');

    viewButtons.forEach(button => {
        button.addEventListener('click', function() {
            viewButtons.forEach(b => b.classList.remove('active'));
            this.classList.add('active');
            
            if (this.dataset.view === 'map') {
                mapContainer.style.display = 'block';
                listingsGrid.style.display = 'none';
                // Ensure map is properly loaded
                if (mapFrame) {
                    mapFrame.src = mapFrame.src;
                }
            } else {
                mapContainer.style.display = 'none';
                listingsGrid.style.display = 'block';
            }
        });
    });
});
