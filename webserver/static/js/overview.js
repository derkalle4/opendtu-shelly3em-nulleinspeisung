document.addEventListener("pulledData", e => {
    // update current status chart
    update_chart_current_status(
        new Date().toLocaleTimeString('de-DE', {
            hour: '2-digit',
            minute: '2-digit',
            second: '2-digit'
        }),
        e.detail.data
    );
});