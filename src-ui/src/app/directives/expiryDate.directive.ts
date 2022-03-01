import { AbstractControl, ValidationErrors, ValidatorFn } from "@angular/forms";

export const expiryDateValidator: ValidatorFn = (control: AbstractControl): ValidationErrors | null => {
    console.log('expiryDateValidator');
    
        const created = control.get('created')
        
        const expired = control.get('expired')
        
        let expiredDate = new Date(expired.value);
        let createdDate = new Date(created.value);

        console.log('TrueFalse');
        console.log(createdDate >= expiredDate );

    
    return createdDate >= expiredDate ? { expiredDateInvalid: true } : null;
  };