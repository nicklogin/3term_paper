var extralingFormId = 0;


var addOneMore = function() {
    if (extralingFormId < 6) {
        zeroForm = document.getElementById("extraLing0");
        extralingFormId += 1;
        newForm = zeroForm.cloneNode(true);
        newForm.id = "extraLing" + extralingFormId;
        extralings = newForm.childNodes;
        extralings.forEach(function(item){
            if (item.name != null) {
                item.name = item.name.split('-')[0].slice(0, -1) + extralingFormId + "-" + item.name.split('-')[1];
            }
        });
        deleteButton = document.createElement("input");
        deleteButton.type = "button";
        deleteButton.value = "-";
        deleteButton.onclick = function() {
            extralingFormId -= 1;
            this.parentNode.parentNode.removeChild(this.parentNode);
        };
        newForm.appendChild(deleteButton);
        newForm.appendChild(document.createElement("br"))
        document.getElementById("extraLing").appendChild(newForm);
    }
};

var addDependant = function(elem) {
    dependantForm = elem.cloneNode(true);
    dependantForm.insertBefore(document.createElement("br"), dependantForm.firstChild);

    //creating dependecy type selector:
    depSelector = document.getElementById("depTypes").cloneNode(true);
    depSelector.hidden = false;
    depSelector.id = "depType" + elem.id;
    depSelector.name = "var"+elem.id.slice(4)+"-typerel";
    dependantForm.insertBefore(depSelector, dependantForm.firstChild);
    dependantForm.innerHTML = "Select dependency type: " + dependantForm.innerHTML;

    // creating form for dependency:
    dependantForm.id = "dependant" + elem.id;
    // delete "add dependency" button:
    button = dependantForm.lastElementChild.previousElementSibling;
    dependantForm.removeChild(button);
    // end of deletion
    fields = dependantForm.childNodes;
    fields.forEach(function(item){
        if (item.name != null) {
            item.name += "Dep";
        }
    });
    elem.appendChild(dependantForm);

    //changing itemType field value:
    itypeField = document.getElementById("itemType"+elem.id);
    itypeField.value = "syntPair";

    // changing 'Add dependency' button behaviour:
    butt = document.getElementById("button"+elem.id);
    butt.onclick = function() {
        deleteDependant(this.parentNode);
    };
    butt.innerHTML = "Delete dependency";
};

var deleteDependant = function(elem) {
    console.log("Entered deleteDependant function");
    console.log(elem);
    // deleting syntactic dependency:
    dependant = document.getElementById("dependant"+elem.id);
    dependant.remove();

    //changing itemType field value:
    itypeField = document.getElementById("itemType"+elem.id);
    itypeField.value = "singleItem";
    
    // changing 'Add dependency' button behaviour:
    butt = document.getElementById("button"+elem.id);
    butt.onclick = function() {
        addDependant(this.parentNode);
    };
    butt.innerHTML = "Add dependency";
};