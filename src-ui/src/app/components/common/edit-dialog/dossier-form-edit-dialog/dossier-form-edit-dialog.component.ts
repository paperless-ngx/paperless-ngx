import { Component, OnInit } from '@angular/core'
import { FormGroup, FormControl } from '@angular/forms'
import { NgbActiveModal } from '@ng-bootstrap/ng-bootstrap'
import { UserService } from 'src/app/services/rest/user.service'
import { SettingsService } from 'src/app/services/settings.service'
import { EditDialogComponent, EditDialogMode } from '../edit-dialog.component'
import { Dossier, DossierType } from 'src/app/data/dossier'
import { DossierService } from 'src/app/services/rest/dossier.service'
import { DossierForm } from 'src/app/data/dossier-form'
import { DossierFormService } from 'src/app/services/rest/dossier-forms.service'

@Component({
  selector: 'pngx-dossier-form-edit-dialog',
  templateUrl: './dossier-form-edit-dialog.component.html',
  styleUrls: ['./dossier-form-edit-dialog.component.scss'],
})
export class DossierFormEditDialogComponent
  extends EditDialogComponent<DossierForm>
  implements OnInit {
  DOSSIER_TYPES_OPTIONS = [

    {
      label: $localize`Document`,
      value: DossierType.Document,
    },
    {
      label: $localize`Dossier`,
      value: DossierType.Dossier,
    },
  ]
  constructor(
    service: DossierFormService,
    activeModal: NgbActiveModal,
    userService: UserService,
    settingsService: SettingsService
  ) {
    super(service, activeModal, userService, settingsService)
  }

  ngOnInit(): void {
    super.ngOnInit()
    if (this.typeFieldDisabled) {
    }
  }

  getCreateTitle() {
    return $localize`Create new dossier form`
  }

  getEditTitle() {
    return $localize`Edit dossier form`
  }
  dataCustomFields:any[] =[]
  getForm(): FormGroup {
    return new FormGroup({
      name: new FormControl(null),
      form_rule: new FormControl(null),
      type: new FormControl(DossierType.Dossier),
      permissions_form: new FormControl(null),
      custom_fields: new FormControl([]),
      
    })
  }

  onDataChange(data: any[]) {
    this.dataCustomFields=data
    // this.getForm().patchValue({ custom_fields1: data });
    // Xử lý dữ liệu ở đây
  }


  save(){
    let getFormOrgin = super.getFormOrigin()
    // getFormOrgin.get('custom_fields').setValue(this.dataCustomFields)
    getFormOrgin.patchValue({ custom_fields: this.dataCustomFields });
  
    super.save()

  }

  get typeFieldDisabled(): boolean {
    return this.dialogMode === EditDialogMode.EDIT
  }

  
}
