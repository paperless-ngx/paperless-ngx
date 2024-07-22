import { Component } from '@angular/core'
import { NgbModal } from '@ng-bootstrap/ng-bootstrap'
import { Subject } from 'rxjs'
import { ToastService } from 'src/app/services/toast.service'
import { DossierEditDialogComponent } from '../../common/edit-dialog/dossier-edit-dialog/dossier-edit-dialog.component'
import { Router } from '@angular/router';
import { ActivatedRoute } from '@angular/router';
import { DocumentListViewService } from 'src/app/services/document-list-view.service'
import { FILTER_HAS_FOLDER_ANY } from 'src/app/data/filter-rule-type'
import {
  PermissionsService,
  PermissionType,
} from 'src/app/services/permissions.service'
import { CustomDossierListComponent } from '../custom-dossier-list/custom-dossier-list.component'
import { DossierService } from 'src/app/services/rest/dossier.service'
import { Dossier } from 'src/app/data/dossier'
import { FolderEditDialogComponent } from '../../common/edit-dialog/folder-edit-dialog/folder-edit-dialog.component'


@Component({
  selector: 'pngx-dossiers',
  templateUrl: './../custom-dossier-list/custom-dossier-list.component.html',
  styleUrls: ['./../custom-dossier-list/custom-dossier-list.component.scss'],
})
export class DossiersComponent
extends CustomDossierListComponent<Dossier> {
  // id: number;
  dossierUnsubscribeNotifier: Subject<any> = new Subject();
  dossier_nameFilter: string;
  MyunsubscribeNotifier: Subject<any> = new Subject()
  constructor(
    private route: ActivatedRoute,
    private router: Router,
    dossierService: DossierService,
    modalService: NgbModal,
    toastService: ToastService,
    documentListViewService: DocumentListViewService,
    permissionsService: PermissionsService,
  ) {
    super(
      dossierService,
      modalService,
      DossierEditDialogComponent,
      toastService,
      documentListViewService,
      permissionsService,
      FILTER_HAS_FOLDER_ANY,
      $localize`dossier`,
      $localize`dossiers`,
      PermissionType.Dossier,
      [],
      dossierService,
      false
    )
    
  }
  
  
  reloadData() {
    this.id = this.route.snapshot.params['id']
    super.reloadData()
  }

  goToDossierDocument(object: Dossier) {
    // this.id = this.route.snapshot.params['id'];
    if(object){
      this.id = object?.id
      this.router.navigate(['/dossiers/', object.id]);
      
    }else{
      this.router.navigate(['/dossiers/',]);
    }
    super.reloadData()

    
   
  }
  goToDossier() {
      super.reloadData()
      this.router.navigate(['/dossiers/',]);
    
  }
    
  getDeleteMessage(object: Dossier) {
    return $localize`Do you really want to delete the dossier "${object.name}"?`
  }
}
