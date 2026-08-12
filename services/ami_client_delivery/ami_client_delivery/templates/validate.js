document.addEventListener('DOMContentLoaded', function() {
    const form = document.getElementById('delivery-form');
    if (form) {
        form.addEventListener('submit', function(event) {
            const submitter_button = event.submitter;

            if (submitter_button && submitter_button.id === 'save'){
                return
            }

            const clientNotes = document.getElementById('client_notes');
            if (clientNotes && !clientNotes.value.trim()) {
                alert('Client Notes should not be empty.');
                event.preventDefault();
                return;
            }

            const clientNames = document.querySelectorAll('[name$="__client_name"]');
            for (let i = 0; i < clientNames.length; i++) {
                if (!clientNames[i].value.trim()) {
                    alert('All version client names should not be empty.');
                    event.preventDefault();
                    return;
                }
            }
        });
    }
});
