// Auto-populate department head when department is selected (Program admin)
(function() {
    document.addEventListener('DOMContentLoaded', function() {
        var deptSelect = document.getElementById('id_department');
        var headNameInput = document.getElementById('id_department_head_name');
        var headEmailInput = document.getElementById('id_department_head_email');
        var headPhoneInput = document.getElementById('id_department_head_phone');

        if (!deptSelect || !headNameInput) return;

        var baseUrl = document.body.getAttribute('data-dept-head-base') || '';
        if (!baseUrl) return;

        function fetchAndPopulate(deptId) {
            if (!deptId || deptId === '') return;
            var url = baseUrl + deptId + '/';
            fetch(url, {
                headers: { 'X-Requested-With': 'XMLHttpRequest' },
                credentials: 'same-origin'
            })
            .then(function(r) { return r.json(); })
            .then(function(data) {
                if (data.head_name) headNameInput.value = data.head_name;
                if (headEmailInput && data.head_email) headEmailInput.value = data.head_email;
                if (headPhoneInput && data.head_phone) headPhoneInput.value = data.head_phone;
            })
            .catch(function() {});
        }

        deptSelect.addEventListener('change', function() {
            fetchAndPopulate(this.value);
        });

        if (deptSelect.value) {
            fetchAndPopulate(deptSelect.value);
        }
    });
})();
