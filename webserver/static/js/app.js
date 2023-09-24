document.addEventListener("DOMContentLoaded", function () {
    // pulls data in a second
    setTimeout(pullData, 1000);
});


async function pullData() {
    fetch('/pull')
        .then((response) => response.json())
        .then((data) => {
            var dom = document.querySelectorAll('[data-pull]');
            [].forEach.call(dom, function (element) {
                let tmpData = element.attributes['data-pull'].value;
                // get pulled data and try to match it to the DOM element
                if (!tmpData.includes('.')) {
                    tmpData = data[tmpData];
                } else {
                    let tmpDataSplit = tmpData.split('.');
                    if (tmpDataSplit.length == 2) tmpData = data[tmpDataSplit[0]][tmpDataSplit[1]];
                    else if (tmpDataSplit.length == 3) tmpData = data[tmpDataSplit[0]][tmpDataSplit[1]][tmpDataSplit[2]];
                    else if (tmpDataSplit.length == 4) tmpData = data[tmpDataSplit[0]][tmpDataSplit[1]][tmpDataSplit[2]][tmpDataSplit[3]];
                    else if (tmpDataSplit.length == 5) tmpData = data[tmpDataSplit[0]][tmpDataSplit[1]][tmpDataSplit[2]][tmpDataSplit[3]][tmpDataSplit[4]];
                    else if (tmpDataSplit.length == 6) tmpData = data[tmpDataSplit[0]][tmpDataSplit[1]][tmpDataSplit[2]][tmpDataSplit[3]][tmpDataSplit[4]][tmpDataSplit[5]];
                    else if (tmpDataSplit.length == 7) tmpData = data[tmpDataSplit[0]][tmpDataSplit[1]][tmpDataSplit[2]][tmpDataSplit[3]][tmpDataSplit[4]][tmpDataSplit[5]][tmpDataSplit[6]];
                    else if (tmpDataSplit.length == 8) tmpData = data[tmpDataSplit[0]][tmpDataSplit[1]][tmpDataSplit[2]][tmpDataSplit[3]][tmpDataSplit[4]][tmpDataSplit[5]][tmpDataSplit[6]][tmpDataSplit[7]];
                    else if (tmpDataSplit.length == 9) tmpData = data[tmpDataSplit[0]][tmpDataSplit[1]][tmpDataSplit[2]][tmpDataSplit[3]][tmpDataSplit[4]][tmpDataSplit[5]][tmpDataSplit[6]][tmpDataSplit[7]][tmpDataSplit[8]];
                }
                // set text of the element if it changed
                if (element.innerText != tmpData) {
                    // set element text
                    element.innerText = tmpData;
                    // get element next to the parent element
                    let elementNext = element.nextElementSibling;
                    // append text to elementNext and remove it after 3 seconds
                    setTimeout(function () {
                        elementNext.innerHTML = elementNext.attributes['data-value'].value;
                    }, 1000);
                    elementNext.setAttribute("data-value", elementNext.innerText);
                    elementNext.innerHTML = elementNext.innerHTML + ' <img src="/static/icons/arrow-clockwise.svg" alt="value updated" class="svg-green"/>';
                }
            });
        });
    // pulls data in a second
    setTimeout(pullData, 1000);
}
