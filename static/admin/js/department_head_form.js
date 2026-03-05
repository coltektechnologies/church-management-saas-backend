// Handle member dropdown based on selected church
document.addEventListener('DOMContentLoaded', function() {
    const churchSelect = document.getElementById('id_church');
    const memberSelect = document.getElementById('id_member');
    const departmentSelect = document.getElementById('id_department');

    // Function to update member dropdown
    function updateMemberDropdown(churchId) {
        if (!churchId) {
            memberSelect.innerHTML = '<option value="">---------</option>';
            return;
        }

        // Fetch members for the selected church
        fetch(`/api/members/?church_id=${churchId}&format=json`)
            .then(response => response.json())
            .then(data => {
                let options = '<option value="">---------</option>';
                data.results.forEach(member => {
                    options += `<option value="${member.id}">${member.full_name}</option>`;
                });
                memberSelect.innerHTML = options;
            })
            .catch(error => console.error('Error fetching members:', error));
    }

    // Function to update department dropdown based on church
    function updateDepartmentDropdown(churchId) {
        if (!churchId) {
            departmentSelect.innerHTML = '<option value="">---------</option>';
            return;
        }

        // Fetch departments for the selected church
        fetch(`/api/departments/?church_id=${churchId}&format=json`)
            .then(response => response.json())
            .then(data => {
                let options = '<option value="">---------</option>';
                data.results.forEach(dept => {
                    options += `<option value="${dept.id}">${dept.name}</option>`;
                });
                departmentSelect.innerHTML = options;
            })
            .catch(error => console.error('Error fetching departments:', error));
    }

    // Initial setup if church is already selected
    if (churchSelect && churchSelect.value) {
        updateMemberDropdown(churchSelect.value);
        updateDepartmentDropdown(churchSelect.value);
    }

    // Add change event listeners
    if (churchSelect) {
        churchSelect.addEventListener('change', function() {
            updateMemberDropdown(this.value);
            updateDepartmentDropdown(this.value);
        });
    }
});
