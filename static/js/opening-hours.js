/**
 * Checks if a business is currently open based on its hours
 * Uses the user's local timezone for accurate results
 */
document.addEventListener('DOMContentLoaded', function() {
    const openStatusElement = document.getElementById('open-status');
    
    // If there's no status element on the page, exit early
    if (!openStatusElement) return;
    
    // Get hours data from the data attribute
    const hoursDataString = openStatusElement.getAttribute('data-hours');
    if (!hoursDataString) return;
    
    try {
        // The hours data is already a JavaScript object (parsed by Jinja's tojson filter)
        const hoursData = JSON.parse(hoursDataString);
        const currentStatus = checkIfOpen(hoursData);
        
        // Update the status element
        openStatusElement.textContent = currentStatus.status;
        openStatusElement.className = currentStatus.status_class;
    } catch (error) {
        console.error('Error parsing hours data:', error);
        // Fallback to unknown status
        openStatusElement.textContent = "Hours not available";
        openStatusElement.className = "unknown";
    }
});

/**
 * Determines if a business is currently open based on hours data
 * @param {Object} hoursData - Object with days of week as keys and hour ranges as values
 * @returns {Object} Status object with is_open, status text, and status_class
 */
function checkIfOpen(hoursData) {
    const now = new Date();
    const currentDay = now.toLocaleDateString('en-US', { weekday: 'long' }); // Returns "Monday", "Tuesday", etc.
    const currentHour = now.getHours();
    const currentMinute = now.getMinutes();
    const currentTime = currentHour * 100 + currentMinute; // Convert to HHMM format
    
    // Get today's hours string
    const todayHours = hoursData[currentDay];

    // Handle cases where hours aren't specified
    if (!todayHours || todayHours === "Not specified" || todayHours === "Not Found" || todayHours === "Error parsing hours") {
        return {
            is_open: false,
            status: "Hours not available",
            status_class: "unknown"
        };
    }
    
    // Split multiple time ranges (if any)
    const timeRanges = todayHours.split(",").map(range => range.trim());
    
    for (const timeRange of timeRanges) {
        try {
            const [openTimeStr, closeTimeStr] = timeRange.split("-").map(t => t.trim());
            
            // Parse opening time
            const openMatch = openTimeStr.toUpperCase();
            let openHour, openMinute;
            
            if (openMatch.includes(':')) {
                openHour = parseInt(openMatch.split(":")[0]);
                openMinute = parseInt(openMatch.split(":")[1].split(/\s+/)[0]);
            } else {
                openHour = parseInt(openMatch.split(/\s+/)[0]);
                openMinute = 0;
            }
            
            if (openMatch.includes('PM') && openHour !== 12) {
                openHour += 12;
            } else if (openMatch.includes('AM') && openHour === 12) {
                openHour = 0;
            }
            
            const openTime = openHour * 100 + openMinute;
            
            // Parse closing time
            const closeMatch = closeTimeStr.toUpperCase();
            let closeHour, closeMinute;
            
            if (closeMatch.includes(':')) {
                closeHour = parseInt(closeMatch.split(":")[0]);
                closeMinute = parseInt(closeMatch.split(":")[1].split(/\s+/)[0]);
            } else {
                closeHour = parseInt(closeMatch.split(/\s+/)[0]);
                closeMinute = 0;
            }
            
            if (closeMatch.includes('PM') && closeHour !== 12) {
                closeHour += 12;
            } else if (closeMatch.includes('AM') && closeHour === 12) {
                closeHour = 0;
            }
            
            const closeTime = closeHour * 100 + closeMinute;
            
            // Check if current time falls within range
            if (currentTime >= openTime && currentTime <= closeTime) {
                const closingTime = new Date();
                closingTime.setHours(closeHour);
                closingTime.setMinutes(closeMinute);
                
                // Format closing time as "1:30 PM" format
                const formattedClosingTime = closingTime.toLocaleTimeString('en-US', {
                    hour: 'numeric',
                    minute: '2-digit',
                    hour12: true
                });
                
                return {
                    is_open: true,
                    status: `Open Now · Closes ${formattedClosingTime}`,
                    status_class: "open"
                };
            }
        } catch (error) {
            console.error('Error parsing time range:', timeRange, error);
            continue;
        }
    }
    
    return {
        is_open: false,
        status: "Closed Now",
        status_class: "closed"
    };
}
