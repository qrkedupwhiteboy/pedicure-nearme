document.addEventListener('DOMContentLoaded', function() {
    const faqItems = document.querySelectorAll('.collapse-item');
    
    faqItems.forEach(item => {
        const title = item.querySelector('.collapse-title');
        
        title.addEventListener('click', () => {
            // Close all other items
            faqItems.forEach(otherItem => {
                if (otherItem !== item && otherItem.classList.contains('expanded')) {
                    otherItem.classList.remove('expanded');
                }
            });
            
            // Toggle current item
            item.classList.toggle('expanded');
        });
    });
});
