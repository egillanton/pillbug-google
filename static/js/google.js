function send() {
    if ($("#title_input").val() && $("#time_str_input").val()) {
        $("#btn-send").attr("disabled", true);

        $.ajax({
            type: 'POST',
            url: "/remind",
            contentType: "application/json; charset=utf-8",
            dataType: "json",
            data: JSON.stringify({
                "title": $("#title_input").val(),
                "time_str": $("#time_str_input").val(),
            }),
            success: function (res) {
                $("#response_textarea").val(`A reminder has been successfully created and added to your Google Calander:\n${res.response}`)
                $("#response_area").css('display', 'block');
            },
            error: function (error) {
                console.log(error);
                $("#response_textarea").val(`ERROR Accured:\n${error}`)
                $("#response_area").css('display', 'block');
            },
            complete: function (data) {
                $("#btn-send").attr("disabled", false);
            }
        });
    }
}


$(document).ready(function () {
    $("#btn-send").attr("disabled", false);

    $("#title_input").val("Give Sarah 2 pills of Valacyclovir");
    $("#time_str_input").val("Tomorrow at 8am");

    $("#btn-send").click(function (e) {
        send();
    });
});