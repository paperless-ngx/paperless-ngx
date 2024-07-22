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
  // private readonly dossierService: DossierService
  private unsubscribeNotifier: Subject<any> = new Subject()
  dossier: Dossier[]=[]
  dataCustomFields: any[]=[]
  dataFromCustomFields: any[]=[]
  constructor(
    service: DossierService,
    activeModal: NgbActiveModal,
    userService: UserService,
    settingsService: SettingsService,
    private readonly dossierService: DossierService
  ) {
    super(service, activeModal, userService, settingsService)
    // this.dataDossier()
    // this.getFormOrigin().get('parent_dossier_type').setValue(null)
    console.log(this.getFormOrigin().value)
    // if(this.getFormOrigin().get('dossier_type').value==DossierType.Document){
    //   this.dataDossier(DossierType.Document)
      
    //   // this.dataCustomFields = 
    // }
    // else if(this.getFormOrigin().get('dossier_type').value==DossierType.Dossier){
    //   this.dataDossier(DossierType.Dossier)
      
    // }

    this.getFormOrigin().valueChanges.subscribe(value => {
      
      // console.log(value)
      if(value.dossier_type==DossierType.Document){
        this.dataDossier(DossierType.Document)
        
        // this.dataCustomFields = 
      }
      else if(value.dossier_type==DossierType.Dossier){
        this.dataDossier(DossierType.Dossier)
        
      }

      // console.log(this.getFormOrigin().value)
      // const dossierSelect = this.dossier.find(obj => obj.id === value.id);
      // if (dossierSelect) {
      //   this.dataCustomFields=dossierSelect.custom_fields
      // } else {
      //   console.log("Object not found.");
      // }
      
    });
   
  }

  ngOnInit(): void {
    super.ngOnInit()
    if (this.typeFieldDisabled) {
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
      parent_dossier_type: new FormControl(null),
      dossier_type: new FormControl(null),
      permissions_form: new FormControl(null),
      custom_fields: new FormControl([]),
    })
  }
  dataDossier(type){
    this.dossierService
      .listDossierFiltered(
        1,
        null,
        null,
        null,
        null,
        true,
        null,
        true,
        type
      )
      .pipe(takeUntil(this.unsubscribeNotifier))
      .subscribe((c) => {
        this.dossier = c.results
        
        const dossierSelect = this.dossier.find(obj => obj.id === this.getFormOrigin().value.parent_dossier_type);
        if (dossierSelect) {
          
          console.log(this.getFormOrigin().value)
          this.dataCustomFields=dossierSelect.custom_fields
        } else {
          console.log("Object not found.");
        }
        
      })  
  }


  onDataInputChange(data) {
   
    this.getFormOrigin().get('parent_dossier_type').setValue(null)
    
    // this.dataCustomFields=null
    // if(data==DossierType.Document){
    //   this.dataDossier(DossierType.Document)
      
    // }
    // else if(data==DossierType.Dossier){
    //   this.dataDossier(DossierType.Dossier)
    // }
      
      

  }
  onDataInputParentDossierTypeChange(data) {
    this.dataCustomFields=[]
    const dossierSelect = this.dossier.find(obj => obj.id === data);
    if (dossierSelect) {
      this.getFormOrigin().patchValue({ custom_fields: this.dataFromCustomFields });
    } else {
      console.log("Object not found.");
    }
  

  }
  onDataChange(data) {
    this.dataFromCustomFields=data

  }

  save(){
    let getFormOrgin = super.getFormOrigin()
    // getFormOrgin.get('custom_fields').setValue(this.dataCustomFields)
    getFormOrgin.patchValue({ custom_fields: this.dataFromCustomFields });
  
    super.save()

  }

  get typeFieldDisabled(): boolean {
    return this.dialogMode === EditDialogMode.EDIT
  }
}
