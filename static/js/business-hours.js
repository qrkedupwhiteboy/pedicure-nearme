function isBusinessOpen(hoursData) {
    // Get current date/time
    const now = new Date();
    const currentDay = now.toLocaleString('en-us', {weekday: 'long'}); // Returns "Monday", "Tuesday", etc.
    const currentTime = now.getHours() * 100 + now.getMinutes(); // Convert to HHMM format

    // Get today's hours string
    const todayHours = hoursData[currentDay];
    
    // Handle cases where hours aren't specified
    if (!todayHours || todayHours === 'Not specified' || todayHours === 'Not Found' || todayHours === 'Error parsing hours') {
        return {
            isOpen: false,
            status: 'Hours not available'
        };
    }

    // Split multiple time ranges (if any)
    const timeRanges = todayHours.split(',').map(range => range.trim());
    
    for (const range of timeRanges) {
        // Extract opening and closing times
        const [openTime, closeTime] = range.split('-').map(time => {
            const [hours, minutes, period] = time.trim().match(/(\d+):(\d+)\s*(AM|PM)/i).slice(1);
            let militaryHours = parseInt(hours);
            
            // Convert to 24-hour format
            if (period.toUpperCase() === 'PM' && militaryHours !== 12) {
                militaryHours += 12;
            } else if (period.toUpperCase() === 'AM' && militaryHours === 12) {
                militaryHours = 0;
            }
            
            return militaryHours * 100 + parseInt(minutes);
        });

        // Check if current time falls within this range
        if (currentTime >= openTime && currentTime <= closeTime) {
            return {
                isOpen: true,
                status: 'Open Now',
                closingTime: closeTime
            };
        }
    }

    return {
        isOpen: false,
        status: 'Closed Now'
    };
}

function updateOpenStatus(hoursData) {
    const statusElement = document.getElementById('open-status');
    if (!statusElement) return;

    const status = isBusinessOpen(hoursData);
    
    // Remove any existing classes
    statusElement.classList.remove('open', 'closed', 'unknown');
    
    if (status.isOpen) {
        statusElement.classList.add('open');
        const closeTime = new Date();
        closeTime.setHours(Math.floor(status.closingTime / 100));
        closeTime.setMinutes(status.closingTime % 100);
        statusElement.textContent = `Open Now · Closes ${closeTime.toLocaleTimeString([], {hour: 'numeric', minute:'2-digit'})}`;
    } else {
        statusElement.classList.add(status.status === 'Hours not available' ? 'unknown' : 'closed');
        statusElement.textContent = status.status;
    }
}
