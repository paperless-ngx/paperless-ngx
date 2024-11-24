import { Component, QueryList, Renderer2, ViewChild, ViewChildren } from '@angular/core'
import { NgbModal, NgbPopover } from '@ng-bootstrap/ng-bootstrap'
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
import { DocumentService } from '../../../services/rest/document.service'
import { Document } from '../../../data/document'


@Component({
  selector: 'pngx-folders',
  templateUrl: './../custom-folder-list/custom-folder-list.component.html',
  styleUrls: ['./../custom-folder-list/custom-folder-list.component.scss'],
})
export class FoldersComponent
extends CustomFolderListComponent<Folder> {


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
    public documentService: DocumentService
  ) {
    function formatBytes(bytes, decimals = 2) {
        if (!+bytes) return '0 Bytes'

        const k = 1024
        const dm = decimals < 0 ? 0 : decimals
        const sizes = ['Bytes', 'KB', 'MB', 'GB', 'TB', 'PB', 'EB', 'ZB', 'YB']

        const i = Math.floor(Math.log(bytes) / Math.log(k))

        return `${parseFloat((bytes / Math.pow(k, i)).toFixed(dm))} ${sizes[i]}`
    }

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
      [{key: 'filesize', name: 'Size', valueFn: (item) => (item.type == 'file')?formatBytes(item.filesize):"", rendersHtml: true}],
      folderService
    )
  }
  @ViewChildren('popover') popovers: QueryList<NgbPopover>
  popover: NgbPopover
  mouseOnPreview = false
  popoverHidden = true



  extractDocuments(): void {
    console.log("dax goi")
    this.documents = this.data
      .filter(item => item.document)  // Lọc các phần tử có `document`
      .map(item => item.document);    // Chỉ lấy phần `document` của các phần tử
  }
  reloadData() {
    this.id = this.route.snapshot.params['id'] !== 'root' ? this.route.snapshot.params['id'] :  null;
    super.reloadData()
  }

  getPreviewUrl(document: Document): string {
    return this.documentService.getPreviewUrl(document.id)
  }

  mouseEnterPreviewButton(doc: Document) {
    const newPopover = this.popovers.get(this.documents.indexOf(doc))
    if (this.popover !== newPopover && this.popover?.isOpen())
      this.popover.close()
    this.popover = newPopover
    this.mouseOnPreview = true
    if (!this.popover.isOpen()) {

      this.popoverHidden = true
      setTimeout(() => {
        if (this.mouseOnPreview) {
          // show popover
          this.popover.open()
          this.popoverHidden = false
        } else {
          this.popover.close()
        }
      }, 600)
    }
  }

  mouseLeavePreviewButton() {
    this.mouseOnPreview = false
    this.maybeClosePopover()
  }
  maybeClosePopover() {
    setTimeout(() => {
      if (!this.mouseOnPreview) this.popover?.close()
    }, 600)
  }
  mouseLeavePreview() {
    this.mouseOnPreview = false
    this.maybeClosePopover()
  }
  mouseEnterPreview() {
      this.mouseOnPreview = true
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
