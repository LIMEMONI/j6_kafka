$(document).ready(function() {
    console.log("문서가 준비되었습니다.");

    // "불러오기" 버튼을 클릭하면 모달을 열도록 합니다.
    document.getElementById("uploadButton").addEventListener("click", function() {
        $('#uploadModal').modal('show');
    });

    // "불러오기" 버튼 클릭 시 데이터를 불러오고 시각화
    document.getElementById("uploadButton").addEventListener("click", function() {
        // 여기에 데이터 불러오는 코드를 추가해야 합니다.
        // 데이터를 불러온 후, 원하는 컬럼을 선택하여 데이터를 가공하세요.
        // 선택한 데이터를 사용하여 D3.js 또는 다른 시각화 라이브러리를 사용하여 그래프를 그립니다.

        // 더 많은 코드를 추가하여 데이터를 처리하고 그래프를 그리세요.

        // D3.js를 사용하여 데이터 시각화
        var width = 400;
        var height = 200;

        var svg = d3.select("#chart")
            .append("svg")
            .attr("width", width)
            .attr("height", height);

        // processedData를 이용하여 그래프를 그리는 코드를 추가하세요.
    });
});

// 파일 업로드 버튼 클릭 시 호출되는 함수
function uploadFile() {
    // 여기에 파일 업로드 및 데이터 처리 코드를 추가하세요.
    // 데이터를 가공하고 시각화를 수행해야 합니다.

    // 예를 들어, 파일을 업로드하고 데이터를 추출하는 방법:
    var fileInput = document.getElementById('csvFile');
    var file = fileInput.files[0];
    var reader = new FileReader();

    reader.onload = function(e) {
        var csvContent = e.target.result;
        // 추출된 CSV 데이터를 가공하고 처리하세요.
        // D3.js 또는 다른 시각화 라이브러리를 사용하여 그래프를 그립니다.
    };

    reader.readAsText(file);
}
