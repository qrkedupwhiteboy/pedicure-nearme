function getCurrentLocation() {
    if (navigator.geolocation) {
        navigator.geolocation.getCurrentPosition(
            function(position) {
                // Success callback
                const latitude = position.coords.latitude;
                const longitude = position.coords.longitude;
                
                // Get location name from coordinates using reverse geocoding
                fetch(`https://nominatim.openstreetmap.org/reverse?format=json&lat=${latitude}&lon=${longitude}`)
                    .then(response => response.json())
                    .then(data => {
                        const locationInput = document.getElementById('location-input');
                        locationInput.value = data.display_name;
                    })
                    .catch(error => {
                        console.error('Error getting location name:', error);
                        alert('Unable to get your location name. Please enter it manually.');
                    });
            },
            function(error) {
                // Error callback
                console.error('Error getting location:', error);
                alert('Unable to get your location. Please enable location services or enter your location manually.');
            }
        );
    } else {
        alert('Geolocation is not supported by your browser. Please enter your location manually.');
    }
}
