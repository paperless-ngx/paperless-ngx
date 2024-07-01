import { Component, HostListener } from '@angular/core'
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
import {Location} from "@angular/common";


@Component({
  selector: 'pngx-folders',
  templateUrl: './../custom-folder-list/custom-folder-list.component.html',
  styleUrls: ['./../custom-folder-list/custom-folder-list.component.scss'],
})
export class SubFoldersComponent
extends CustomFolderListComponent<Folder> {
  // id: number;
  folderUnsubscribeNotifier: Subject<any> = new Subject();
  folder_nameFilter: string;
  constructor(
    private route: ActivatedRoute,
    private router: Router,
    folderService: FolderService,
    modalService: NgbModal,
    toastService: ToastService,
    documentListViewService: DocumentListViewService,
    permissionsService: PermissionsService,
    location: Location,
    
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
      PermissionType.Folder,[],
      folderService
    )
    
  }
 
  @HostListener('window:popstate', ['$event'])
  onPopState(event) {
    this.url = location.pathname.split("/")[2];
    this.id=this.url
    console.log('Back button pressed',this.id);
    super.reloadData()
  }
  reloadData() {
    
    this.id = this.route.snapshot.params['id']
   
    console.log('load trang',this.router.url.split('/')[2])
    super.reloadData()
  }

  goToFolder(object: Folder) {
    // this.id = this.route.snapshot.params['id'];
    this.id = object.id
    super.reloadData()
    this.router.navigate(['/subfolders/', object.id]);
  }
  goToFolderRoot() {
    super.reloadData()
    this.router.navigate(['/folders/',]);
  
}
  getDeleteMessage(object: Folder) {
    return $localize`Do you really want to delete the folder "${object.name}"?`
  }
}
