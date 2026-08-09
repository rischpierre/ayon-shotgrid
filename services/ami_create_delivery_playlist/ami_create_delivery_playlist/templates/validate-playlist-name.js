(function () {
  const NAME_PATTERN = /^delivery_\d{4}-\d{2}-\d{2}_\d{2}$/;
  const TOOLTIP_MESSAGE = "Name must follow the pattern: delivery_YYYY-MM-DD_##";

  const input = document.getElementById("name");
  const field = document.getElementById("name-field");
  if (!input || !field) return;

  function validate() {
    const value = input.value.trim();
    const isValid = value === "" || NAME_PATTERN.test(value);
    field.classList.toggle("invalid", !isValid);
    if (!isValid) {
      field.setAttribute("data-tooltip", TOOLTIP_MESSAGE);
    } else {
      field.removeAttribute("data-tooltip");
    }
    return isValid;
  }

  input.addEventListener("input", validate);
  input.addEventListener("blur", validate);

  const form = input.closest("form");
  if (form) {
    form.addEventListener("submit", (event) => {
      if (!NAME_PATTERN.test(input.value.trim())) {
        field.classList.add("invalid");
        field.setAttribute("data-tooltip", TOOLTIP_MESSAGE);
        event.preventDefault();
        input.focus();
      }
    });
  }
})();
