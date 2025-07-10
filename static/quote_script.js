window.addEventListener('DOMContentLoaded', function() {
    var chartDates = window.chartDates;
    var chartCloses = window.chartCloses;
    if (chartDates && chartCloses) {
        new Chart(document.getElementById('stockChart').getContext('2d'), {
            type: 'line',
            data: {
                labels: chartDates,
                datasets: [{
                    label: 'Close Price',
                    data: chartCloses,
                    borderColor: '#0d6efd',
                    backgroundColor: 'rgba(13,110,253,0.1)',
                    fill: true,
                    tension: 0.2
                }]
            },
            options: {
                scales: {
                    x: { title: { display: true, text: 'Date' } },
                    y: { title: { display: true, text: 'Price (USD)' } }
                }
            }
        });
    }
});
