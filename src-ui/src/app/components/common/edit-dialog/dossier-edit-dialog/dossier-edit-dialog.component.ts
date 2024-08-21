import { Component, OnInit } from '@angular/core'
import { FormGroup, FormControl } from '@angular/forms'
import { NgbActiveModal } from '@ng-bootstrap/ng-bootstrap'
import { UserService } from 'src/app/services/rest/user.service'
import { SettingsService } from 'src/app/services/settings.service'
import { EditDialogComponent, EditDialogMode } from '../edit-dialog.component'
import { Dossier, DossierType } from 'src/app/data/dossier'
import { DossierService } from 'src/app/services/rest/dossier.service'
import { Subject, takeUntil } from 'rxjs'
import { valentine } from 'ngx-bootstrap-icons'
import { DossierFormService } from 'src/app/services/rest/dossier-forms.service'

@Component({
  selector: 'pngx-dossier-edit-dialog',
  templateUrl: './dossier-edit-dialog.component.html',
  styleUrls: ['./dossier-edit-dialog.component.scss'],
})

export class DossierEditDialogComponent
  extends EditDialogComponent<Dossier>
  implements OnInit {
  DOSSIER_TYPES_OPTIONS:any[] = [

    {
      label: $localize`Document`,
      id: DossierType.Document,
    },
    {
      label: $localize`Dossier`,
      id: DossierType.Dossier,
    },
   
  ]
  private unsubscribeNotifier: Subject<any> = new Subject()
  dossierArray: Dossier[]=[]
  dataCustomFields: any[]=[]
  dataFromCustomFields: any[]=[]
  constructor(
    service: DossierService,
    activeModal: NgbActiveModal,
    userService: UserService,
    settingsService: SettingsService,
    private readonly dossierService: DossierService,
    private readonly dossierFormService: DossierFormService
  ) {
    super(service, activeModal, userService, settingsService)

    this.getFormOrigin().valueChanges.subscribe(value => {
      
      if(value.type==DossierType.Document){
        this.dataDossier(DossierType.Document)
     
      }
      else if(value.type==DossierType.Dossier){
        this.dataDossier(DossierType.Dossier)
        
      }

    });
   
  }

  ngOnInit(): void {
    super.ngOnInit()
    if (this.typeFieldDisabled) {
    }
    if(this.object){
      // console.log(this.object)

      this.dataCustomFields=this.object.custom_fields
    }
    
    
  }

  getCreateTitle() {
    return $localize`Create new dossier`
  }

  getEditTitle() {
    return $localize`Edit dossier`
  }

  getForm(): FormGroup {
    return new FormGroup({
      name: new FormControl(null),
      dossier_form: new FormControl(null),
      type: new FormControl(null),
      permissions_form: new FormControl(null),
      custom_fields: new FormControl([]),
    })
  }
  dataDossier(type){
    this.dossierFormService
      .listDossierFormFiltered(1,null,null,null,null,null,true,type)
      .pipe(takeUntil(this.unsubscribeNotifier))
      .subscribe((c) => {
        this.dossierArray = c.results
        
      })  
  }


  onDataInputChange(data) {
    this.getFormOrigin().get('dossier_form').setValue(null)    
  }
  onDataInputParentDossierTypeChange(data) {
    this.dataCustomFields=[]
    const dossierSelect = this.dossierArray.find(obj => obj.id === this.getFormOrigin().get('dossier_form').value);
    
    if (dossierSelect) {
      this.dataCustomFields = dossierSelect.custom_fields
      // this.getFormOrigin().patchValue({ custom_fields: this.dataFromCustomFields });
    } 

  }
  onDataChange(data) {
    this.dataFromCustomFields=data

  }

  save(){
    let getFormOrgin = super.getFormOrigin()
    getFormOrgin.patchValue({ custom_fields: this.dataFromCustomFields });
  
    super.save()

  }

  get typeFieldDisabled(): boolean {
    return this.dialogMode === EditDialogMode.EDIT
  }
}
