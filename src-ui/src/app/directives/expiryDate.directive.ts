import { AbstractControl, ValidationErrors, ValidatorFn } from "@angular/forms";

export const expiryDateValidator: ValidatorFn = (control: AbstractControl): ValidationErrors | null => {
    const created = control.get("created");
    const expired = control.get("expired");
    let expiredDate = new Date(expired.value);
    let createdDate = new Date(created.value);
    return createdDate >= expiredDate ? { expiredDateInvalid: true } : null;
  };