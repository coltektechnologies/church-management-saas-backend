// This file handles the dynamic updating of member and department dropdowns
// based on the selected church in the DepartmentHead admin form

// Helper function to get cookie value by name
function getCookie(name) {
    let cookieValue = null;
    if (document.cookie && document.cookie !== '') {
        const cookies = document.cookie.split(';');
        for (let i = 0; i < cookies.length; i++) {
            const cookie = cookies[i].trim();
            // Does this cookie string begin with the name we want?
            if (cookie.substring(0, name.length + 1) === (name + '=')) {
                cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                break;
            }
        }
    }
    return cookieValue;
}

document.addEventListener('DOMContentLoaded', function() {
    // Initialize the form when the page loads
    const churchField = document.getElementById('id_church');
    if (churchField) {
        // If there's already a church selected, update the other fields
        if (churchField.value) {
            updateMemberAndDepartmentDropdowns(churchField);
        }

        // Add event listener for church field changes
        churchField.addEventListener('change', function() {
            updateMemberAndDepartmentDropdowns(this);
        });
    }
});

function updateMemberAndDepartmentDropdowns(churchField) {
    const churchId = churchField.value;
    const memberField = document.getElementById('id_member');
    const departmentField = document.getElementById('id_department');

    // Clear existing options
    if (memberField) {
        memberField.innerHTML = '<option value="">---------</option>';
    }

    if (departmentField) {
        departmentField.innerHTML = '<option value="">---------</option>';
    }

    if (!churchId) {
        return;
    }

    // Fetch members for the selected church
    if (memberField) {
        fetch(`/api/members/members/by-church/?church_id=${churchId}`)
            .then(response => {
                if (!response.ok) {
                    throw new Error(`HTTP error! status: ${response.status}`);
                }
                return response.json();
            })
            .then(data => {
                // Clear existing options except the first one
                memberField.innerHTML = '<option value="">---------</option>';

                data.forEach(member => {
                    const option = document.createElement('option');
                    option.value = member.id;
                    option.textContent = member.name;  // Using the formatted name from the API
                    if (memberField.dataset.selectedValue === member.id) {
                        option.selected = true;
                    }
                    memberField.appendChild(option);
                });
            })
            .catch(error => {
                console.error('Error fetching members:', error);
                memberField.innerHTML = '<option value="">Error loading members</option>';
            });
    }

    // Fetch departments for the selected church
    if (departmentField) {
        // Simple GET request without any authentication
        fetch(`/api/departments/departments/by-church/?church_id=${churchId}`)
            .then(response => {
                if (!response.ok) {
                    throw new Error(`HTTP error! status: ${response.status}`);
                }
                return response.json();
            })
            .then(data => {
                // Clear existing options except the first one
                departmentField.innerHTML = '<option value="">---------</option>';

                data.forEach(department => {
                    const option = document.createElement('option');
                    option.value = department.id;
                    option.textContent = department.name;
                    if (departmentField.dataset.selectedValue === department.id) {
                        option.selected = true;
                    }
                    departmentField.appendChild(option);
                });
            })
            .catch(error => {
                console.error('Error fetching departments:', error);
                departmentField.innerHTML = '<option value="">Error loading departments</option>';
            });
    }
}
