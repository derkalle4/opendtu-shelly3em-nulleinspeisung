document.addEventListener("DOMContentLoaded", function () {
    // render chart
});

const ctx = document.getElementById('chart_current_status');

Chart.defaults.color = '#fff';
var chart_current_status = new Chart(ctx, {
    type: 'line',
    data: {
        labels: [],
        datasets: [{
            id: 'calculated.normalized_sum',
            label: 'Gesamtverbrauch',
            data: [],
            borderColor: 'rgb(255, 0, 0)',
            backgroundColor: 'rgba(255, 0, 0, 0.1)',
            fill: true,
            borderWidth: 3
        },
        {
            id: 'opendtu.0/power',
            label: 'Solarbezug',
            data: [],
            borderColor: 'rgb(0, 255, 0)',
            backgroundColor: 'rgba(0, 255, 0, 0.1)',
            fill: true,
            borderWidth: 3
        },
        {
            id: 'calculated.new_limit',
            label: 'Limit WR',
            data: [],
            borderColor: 'rgb(128, 128, 0)',
            borderWidth: 2,
        }]
    },
    options: {
        animation: false,
        responsive: true,
        maintainAspectRatio: false,
        scales: {
            y: {
                beginAtZero: true
            }
        },
        elements: {
            point: {
                radius: 0
            }
        }
    }
});

async function update_chart_current_status(x_axis, y_axis) {
    // keep only last 10 entries of the chart
    if (chart_current_status.data.labels.length > 50) {
        chart_current_status.data.labels.shift();
        chart_current_status.data.datasets.forEach((dataset) => {
            dataset.data.shift();
        });
    }
    chart_current_status.data.labels.push(x_axis);
    chart_current_status.data.datasets.forEach((dataset) => {
        if (dataset.id in y_axis) dataset.data.push(y_axis[dataset.id]);
    });
    chart_current_status.update();
}