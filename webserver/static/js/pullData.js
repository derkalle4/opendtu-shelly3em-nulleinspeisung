document.addEventListener("DOMContentLoaded", function () {
    // pulls data in a second
    setTimeout(pullData, 1000);
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
                    try {
                        if (tmpDataSplit.length == 2) tmpData = data[tmpDataSplit[0]][tmpDataSplit[1]];
                        else if (tmpDataSplit.length == 3) tmpData = data[tmpDataSplit[0]][tmpDataSplit[1]][tmpDataSplit[2]];
                        else if (tmpDataSplit.length == 4) tmpData = data[tmpDataSplit[0]][tmpDataSplit[1]][tmpDataSplit[2]][tmpDataSplit[3]];
                        else if (tmpDataSplit.length == 5) tmpData = data[tmpDataSplit[0]][tmpDataSplit[1]][tmpDataSplit[2]][tmpDataSplit[3]][tmpDataSplit[4]];
                        else if (tmpDataSplit.length == 6) tmpData = data[tmpDataSplit[0]][tmpDataSplit[1]][tmpDataSplit[2]][tmpDataSplit[3]][tmpDataSplit[4]][tmpDataSplit[5]];
                        else if (tmpDataSplit.length == 7) tmpData = data[tmpDataSplit[0]][tmpDataSplit[1]][tmpDataSplit[2]][tmpDataSplit[3]][tmpDataSplit[4]][tmpDataSplit[5]][tmpDataSplit[6]];
                        else if (tmpDataSplit.length == 8) tmpData = data[tmpDataSplit[0]][tmpDataSplit[1]][tmpDataSplit[2]][tmpDataSplit[3]][tmpDataSplit[4]][tmpDataSplit[5]][tmpDataSplit[6]][tmpDataSplit[7]];
                        else if (tmpDataSplit.length == 9) tmpData = data[tmpDataSplit[0]][tmpDataSplit[1]][tmpDataSplit[2]][tmpDataSplit[3]][tmpDataSplit[4]][tmpDataSplit[5]][tmpDataSplit[6]][tmpDataSplit[7]][tmpDataSplit[8]];
                    } catch (error) {
                        // set default of zero
                        tmpData = 0;
                    }
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
            // create event and push the data object for further actions
            const eventPulledData = new CustomEvent("pulledData", { detail: { data: dataObj } });
            document.dispatchEvent(eventPulledData);
        });
    // pulls data in a second
    setTimeout(pullData, 1000);
}
