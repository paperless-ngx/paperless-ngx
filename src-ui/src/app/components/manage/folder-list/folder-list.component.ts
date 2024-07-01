import { Component } from '@angular/core'
import { NgbModal } from '@ng-bootstrap/ng-bootstrap'
import { Subject } from 'rxjs'
import { FolderService } from 'src/app/services/rest/folder.service'
import { ToastService } from 'src/app/services/toast.service'
import { FolderEditDialogComponent } from '../../common/edit-dialog/folder-edit-dialog/folder-edit-dialog.component'
import { Folder } from 'src/app/data/folder'
import { Router } from '@angular/router';
import { ActivatedRoute } from '@angular/router';
import { DocumentListViewService } from 'src/app/services/document-list-view.service'
import { FILTER_HAS_FOLDER_ANY } from 'src/app/data/filter-rule-type'
import {
  PermissionsService,
  PermissionType,
} from 'src/app/services/permissions.service'
import { CustomFolderListComponent } from '../custom-folder-list/custom-folder-list.component'


@Component({
  selector: 'pngx-folders',
  templateUrl: './../custom-folder-list/custom-folder-list.component.html',
  styleUrls: ['./../custom-folder-list/custom-folder-list.component.scss'],
})
export class FoldersComponent
extends CustomFolderListComponent<Folder> {
  // id: number;
  folderUnsubscribeNotifier: Subject<any> = new Subject();
  folder_nameFilter: string;
  MyunsubscribeNotifier: Subject<any> = new Subject()
  constructor(
    private route: ActivatedRoute,
    private router: Router,
    folderService: FolderService,
    modalService: NgbModal,
    toastService: ToastService,
    documentListViewService: DocumentListViewService,
    permissionsService: PermissionsService
  ) {
    super(
      folderService,
      modalService,
      FolderEditDialogComponent,
      toastService,
      documentListViewService,
      permissionsService,
      FILTER_HAS_FOLDER_ANY,
      $localize`folder`,
      $localize`folders`,
      PermissionType.Folder,
      [],
      folderService
    )
  }
  
  reloadData() {
    this.id = this.route.snapshot.params['id']
    console.log('load trang folder',this.router.getCurrentNavigation())
    super.reloadData()
  }

  goToFolder(object: Folder) {
    // this.id = this.route.snapshot.params['id'];
    this.id = object?.id
    // console.log('trang moi',this.route.snapshot.params['id'])
    this.router.navigate(['/subfolders/', object.id]);
    super.reloadData()

    
   
  }
  goToFolderRoot() {
      super.reloadData()
      this.router.navigate(['/folders/',]);
    
  }
    
  getDeleteMessage(object: Folder) {
    return $localize`Do you really want to delete the folder "${object.name}"?`
  }
}
