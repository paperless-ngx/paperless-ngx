import { Component } from '@angular/core'
import { NgbModal } from '@ng-bootstrap/ng-bootstrap'
import { Subject } from 'rxjs'
import { ToastService } from 'src/app/services/toast.service'
import { Router } from '@angular/router';
import { ActivatedRoute } from '@angular/router';
import { DocumentListViewService } from 'src/app/services/document-list-view.service'
import { FILTER_HAS_FOLDER_ANY } from 'src/app/data/filter-rule-type'
import {
  PermissionsService,
  PermissionType,
  PermissionAction
} from 'src/app/services/permissions.service'
import { CustomDossierFormListComponent } from '../custom-dossier-form-list/custom-dossier-form-list.component'
import { DossierService } from 'src/app/services/rest/dossier.service'
import { Dossier } from 'src/app/data/dossier'
import { DossierFormEditDialogComponent } from 'src/app/components/common/edit-dialog/dossier-form-edit-dialog/dossier-form-edit-dialog.component';
import { DossierForm } from 'src/app/data/dossier-form';
import { DossierFormService } from 'src/app/services/rest/dossier-forms.service';


@Component({
  selector: 'pngx-dossiers-form',
  templateUrl: './../custom-dossier-form-list/custom-dossier-form-list.component.html',
  styleUrls: ['./../custom-dossier-form-list/custom-dossier-form-list.component.scss'],
})
export class DossiersFormComponent
extends CustomDossierFormListComponent<DossierForm> {
  // id: number;
  dossierUnsubscribeNotifier: Subject<any> = new Subject();
  dossier_nameFilter: string;
  constructor(
    private route: ActivatedRoute,
    private router: Router,
    dossierFormService: DossierFormService,
    modalService: NgbModal,
    toastService: ToastService,
    documentListViewService: DocumentListViewService,
    permissionsService: PermissionsService,
  ) {
    super(
      dossierFormService,
      modalService,
      DossierFormEditDialogComponent,
      toastService,
      documentListViewService,
      permissionsService,
      FILTER_HAS_FOLDER_ANY,
      $localize`dossier form`,
      $localize`config dossiers form `,
      PermissionType.Dossier,
      [],
      dossierFormService,
      false
    )
    
  }
  
  
  reloadData() {
    this.id = this.route.snapshot.params['id']
    super.reloadData()
  }

  goToDossierDocument(object: DossierForm) {
    // this.id = this.route.snapshot.params['id'];
    this.id = object?.id
    // console.log('trang moi',this.route.snapshot.params['id'])
    this.router.navigate(['config/dossier-form', object.id]);
    super.reloadData()

    
   
  }
  goToDossier() {
      super.reloadData()
      this.router.navigate(['config/dossier-form',]);
    
  }
    
  getDeleteMessage(object: DossierForm) {
    return $localize`Do you really want to delete the dossier "${object.name}"?`
  }

  
}
