import { Component, Renderer2 } from '@angular/core'
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

  public selectedObjects: Set<number> = new Set()


  constructor(
    private route: ActivatedRoute,
    private router: Router,
    folderService: FolderService,
    modalService: NgbModal,
    toastService: ToastService,
    documentListViewService: DocumentListViewService,
    permissionsService: PermissionsService,
    private renderer: Renderer2,
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
    this.id = this.route.snapshot.params['id'] !== 'root' ? this.route.snapshot.params['id'] :  null;

    super.reloadData()
  }

  getFolderSelect(){
    let folderIds = this.route.snapshot.queryParams['folderIds']||[];
    return   Array.from(folderIds).join('').length
  }

  goToFolder(object: Folder) {
    let folderId = this.route.snapshot.queryParams['folderIds'];
    let getQueryParams: { folderIds?: string };

    if (this.isFolderCutClicked) {
        getQueryParams = {
          folderIds: Array.from(this.folderCut).join(',')
        }
    } else if (folderId) {
      getQueryParams = {
        folderIds: Array.from(folderId).join('')
      };
    } else {
      getQueryParams = {};
    }

    this.id = object?.id

    this.router.navigate(['/folders/', object.id],
      {
        queryParams: getQueryParams
      }
    );
    super.reloadData()

  }

  goToFolderRoot() {
    let folderId = this.route.snapshot.queryParams['folderIds'];
    let getQueryParams: { folderIds?: string };

    if (this.isFolderCutClicked) {
      getQueryParams = {
        folderIds: Array.from(this.folderCut).join(',')
      };
    } else if (folderId) {
      getQueryParams = {
        folderIds: Array.from(folderId).join('')
      };
    } else {
      getQueryParams = {};
    }
    this.id = null;
    this.folderPath = [];
    this.page = 1
    this.router.navigate(['/folders/root',], {
      queryParams: getQueryParams
    });

    super.reloadData()

  }
  isSidebarVisible: boolean = true; // Biến để theo dõi trạng thái của sidebar
  buttonLabel: string = 'Show Tree';
  toggleSidebar(event) {
    const btnElement = event.target as HTMLElement;
    const svgElement = btnElement?.querySelector('svg')
    // const spanElement = btnElement?.querySelector('span')
    // console.log(btnElement)
     if (svgElement.style.transform != '') {
        this.renderer.removeStyle(svgElement, 'transform')
        // this.renderer.setValue(btnElement,'Show tree')

      } else {
        this.renderer.setStyle(svgElement, 'transform', 'rotate(180deg)')
        // this.renderer.setValue(btnElement,'Hidden tree')
        this.renderer.setStyle(svgElement, 'transition', 'transform 0.3s ease')
      }
    // // this.renderer.setStyle(svgElement, 'transition', 'transform 0.3s ease')
    this.buttonLabel = !this.isSidebarVisible ? 'Hide Tree ' : 'Show Tree';
    this.isSidebarVisible = !this.isSidebarVisible; // Đảo ngược trạng thái khi nhấn nút
  }

  getDeleteMessage(object: Folder) {
    return $localize`Do you really want to delete the folder "${object.name}"?`
  }
}
