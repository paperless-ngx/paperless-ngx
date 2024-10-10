import {
  Component, EventEmitter,
  OnDestroy,
  OnInit, Output,
  Renderer2,
  ViewChild,
  ViewContainerRef,
} from '@angular/core'
import { ComponentWithPermissions } from 'src/app/components/with-permissions/with-permissions.component'
import { DocumentListViewService } from '../../../../services/document-list-view.service'
import { Folder } from '../../../../data/folder'
import { FolderService } from '../../../../services/rest/folder.service'

import { HttpClient } from '@angular/common/http'

import { Subscription } from 'rxjs'
import { NodeFileWidgetComponent } from '../folder-node-widget/node-tree-widget.component'


const MAX_ALERTS = 5


@Component({
  selector: 'pngx-file-tree-widget',
  templateUrl: './file-tree-widget.component.html',
  styleUrls: ['./file-tree-widget.component.scss'],
})

export class FileTreeWidgetComponent extends ComponentWithPermissions
  implements OnInit, OnDestroy {
  loading: boolean = true
  isLoading: boolean = false
  @ViewChild('container', { read: ViewContainerRef }) container!: ViewContainerRef

  constructor(
    private http: HttpClient,
    private folderService: FolderService,
    private documentListViewService: DocumentListViewService,
    private viewContainer: ViewContainerRef,
    private renderer: Renderer2,
  ) {
    super()
  }

  @Output() goToFolder = new EventEmitter<any>()
  data = [];
  totalFolder = 0;
  pageNumber: number = 1
  subscription: Subscription

  getFolderList(object: Folder, event) {

    this.folderService.listFolderFiltered(
      1,
      null,
      null,
      true,
      object.id,
      null,
      true,
    ).subscribe((c) => {
      const spanElement = (event.target as HTMLElement).closest('span')
      const tdElement = spanElement.closest('td')
      const svgElement = spanElement?.querySelector('svg')
      const tableElement = tdElement?.querySelector('table')
      if (svgElement.style.transform != '') {
        this.renderer.removeStyle(svgElement, 'transform')
      } else {
        this.renderer.setStyle(svgElement, 'transform', 'rotate(90deg)')
        this.renderer.setStyle(svgElement, 'transition', 'transform 0.3s ease')
      }
      if (tableElement) {
        this.renderer.removeChild(tableElement.parentNode, tableElement)
        return
      }
      if (c.count > 0) {

        const tdElement = (event.target as HTMLElement).closest('td')
        const node = this.viewContainer.createComponent(NodeFileWidgetComponent)
        node.instance.data = c.results
        node.instance.folderId = object.id
        node.instance.totalFolder = c.count
        node.instance.goToFolder.subscribe((object) => {
          this.goToFolder.emit(object)
        })
        const componentElement = node.location.nativeElement
        this.renderer.appendChild(tdElement, componentElement)
        return
      }

    })

  }

  content: string | null = null


  updateContent(content: string): void {
    this.content = content
  }

  ngOnDestroy(): void {
    // this.subscription.unsubscribe()
    return
  }

  ngOnInit(): void {
    this.reload()

  }
  viewMore() {
    this.pageNumber=this.pageNumber+1
    this.reload()
  }
  private reload() {

    this.folderService.listFolderFiltered(
      this.pageNumber,
      null,
      null,
      true,
      null,
      null,
      true,
    ).subscribe((c) => {
      if (this.pageNumber > 1) {
        this.data=this.data.concat(c.results)
        this.isLoading = false
        this.loading = false
        return
      }
      this.data = c.results
      this.totalFolder = c.count
      this.isLoading = false
      this.loading = false
      return
    })
  }


}
