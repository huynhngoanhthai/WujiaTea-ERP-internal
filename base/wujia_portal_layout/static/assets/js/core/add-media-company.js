$(document).ready(function () {
    $('#add-media').click(function (e) {
        console.log("heloooooooooooooooooooooooooo");
        let html = "";
        html += ` 
        <div class="col-md-12 col-lg-4">
                <label>Name media</label>
                <br/>
                <input type="text" id="distric-add-company" class="form-control" name="distric-add-company" placeholder="Distric company" required="1"/>

            </div>
            <div class="col-md-12 col-lg-4">
                <label>State media</label>
                <br/>
                <fieldset class="form-group">
                    <select class="form-control" id="state-media">
                        <option id="banner">Banner</option>
                        <option id="slide">Slide</option>
                    </select>
                </fieldset>
            </div>
            <div class="col-md-12 col-lg-2">
                <label>Image media</label>
                <br/>
                <label for="file_create_company"
                    class="custom-file-upload">
                    Choose a picture
                </label>
                <input id="file_create_company" type="file" accept="image/png, image/jpeg" name="file_create_company" style="display: none;" onchange="readURL(this);" />
            </div>
            <div class="col-md-12 col-lg-2">
                <img id="img-upload" class="img-upload-user-profile" />
            </div>
        `;
        return html;
    })
    $(".add-media-company").html(html);
});