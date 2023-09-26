document.addEventListener("DOMContentLoaded", function () {
    // pulls data in a second
    setTimeout(pullData, 1000);
    // enable tooltips
    var tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'))
    var tooltipList = tooltipTriggerList.map(function (tooltipTriggerEl) {
        return new bootstrap.Tooltip(tooltipTriggerEl)
    })
});

async function pullData() {
    fetch('/pull')
        .then((response) => response.json())
        .then((data) => {
            var dataObj = {};
            var dom = document.querySelectorAll('[data-pull]');
            [].forEach.call(dom, function (element) {
                let tmpKey = element.attributes['data-pull'].value;
                let tmpData = '';
                // get pulled data and try to match it to the DOM element
                if (!tmpKey.includes('.')) {
                    tmpData = data[tmpKey];
                } else {
                    let tmpDataSplit = tmpKey.split('.');
                    if (tmpDataSplit.length == 2) tmpData = data[tmpDataSplit[0]][tmpDataSplit[1]];
                    else if (tmpDataSplit.length == 3) tmpData = data[tmpDataSplit[0]][tmpDataSplit[1]][tmpDataSplit[2]];
                    else if (tmpDataSplit.length == 4) tmpData = data[tmpDataSplit[0]][tmpDataSplit[1]][tmpDataSplit[2]][tmpDataSplit[3]];
                    else if (tmpDataSplit.length == 5) tmpData = data[tmpDataSplit[0]][tmpDataSplit[1]][tmpDataSplit[2]][tmpDataSplit[3]][tmpDataSplit[4]];
                    else if (tmpDataSplit.length == 6) tmpData = data[tmpDataSplit[0]][tmpDataSplit[1]][tmpDataSplit[2]][tmpDataSplit[3]][tmpDataSplit[4]][tmpDataSplit[5]];
                    else if (tmpDataSplit.length == 7) tmpData = data[tmpDataSplit[0]][tmpDataSplit[1]][tmpDataSplit[2]][tmpDataSplit[3]][tmpDataSplit[4]][tmpDataSplit[5]][tmpDataSplit[6]];
                    else if (tmpDataSplit.length == 8) tmpData = data[tmpDataSplit[0]][tmpDataSplit[1]][tmpDataSplit[2]][tmpDataSplit[3]][tmpDataSplit[4]][tmpDataSplit[5]][tmpDataSplit[6]][tmpDataSplit[7]];
                    else if (tmpDataSplit.length == 9) tmpData = data[tmpDataSplit[0]][tmpDataSplit[1]][tmpDataSplit[2]][tmpDataSplit[3]][tmpDataSplit[4]][tmpDataSplit[5]][tmpDataSplit[6]][tmpDataSplit[7]][tmpDataSplit[8]];
                }
                // set data object
                dataObj[tmpKey] = tmpData;
                // set text of the element if it changed
                if (element.innerText != tmpData) {
                    // set element text
                    element.innerText = tmpData;
                    // append text to elementNext and remove it after 3 seconds
                    setTimeout(function () {
                        // remove style attributes
                        element.removeAttribute("style");
                    }, 1000);
                    // set element color to green
                    element.style.color = 'green';
                    // set element font weight to bold
                    element.style.fontWeight = 'bold';
                }
            });
            // update current status chart
            update_chart_current_status(
                new Date().toLocaleTimeString('de-DE', {
                    hour: '2-digit',
                    minute: '2-digit',
                    second: '2-digit'
                }),
                dataObj);
        });
    // pulls data in a second
    setTimeout(pullData, 1000);
}
