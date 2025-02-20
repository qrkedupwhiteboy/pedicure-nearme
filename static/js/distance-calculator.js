// Distance calculation utilities
function calculateDistance(lat1, lon1, lat2, lon2) {
    const R = 3963.1; // Earth's radius in miles
    const dLat = (lat2 - lat1) * Math.PI / 180;
    const dLon = (lon2 - lon1) * Math.PI / 180;
    const a = Math.sin(dLat/2) * Math.sin(dLat/2) +
              Math.cos(lat1 * Math.PI / 180) * Math.cos(lat2 * Math.PI / 180) *
              Math.sin(dLon/2) * Math.sin(dLon/2);
    const c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1-a));
    return R * c;
}

// Update distances after page load
document.addEventListener('DOMContentLoaded', () => {
    const userLat = localStorage.getItem('userLat');
    const userLon = localStorage.getItem('userLon');

    if (userLat && userLon) {
        // Update main listing distance
        const distanceSpan = document.querySelector('.distance-value');
        if (distanceSpan) {
            const listingLat = parseFloat(distanceSpan.dataset.lat);
            const listingLon = parseFloat(distanceSpan.dataset.lon);
            const distance = calculateDistance(
                parseFloat(userLat), 
                parseFloat(userLon), 
                listingLat, 
                listingLon
            );
            distanceSpan.textContent = `${distance.toFixed(1)} mi`;
        }

        // Update nearby listings distances
        document.querySelectorAll('.nearby-card-distance').forEach(span => {
            const nearbyLat = parseFloat(span.dataset.lat);
            const nearbyLon = parseFloat(span.dataset.lon);
            const distance = calculateDistance(
                parseFloat(userLat), 
                parseFloat(userLon), 
                nearbyLat, 
                nearbyLon
            );
            span.textContent = `${distance.toFixed(1)} miles away`;
        });
    }
});
