import {
  Component, EventEmitter,
  OnDestroy,
  OnInit, Output,
  Renderer2,
  ViewChild,
  ViewContainerRef,
} from '@angular/core'
import { ComponentWithPermissions } from 'src/app/components/with-permissions/with-permissions.component'
import { DocumentListViewService } from 'src/app/services/document-list-view.service';
import { Folder } from 'src/app/data/folder'
import { FolderService } from 'src/app/services/rest/folder.service'

import { HttpClient } from '@angular/common/http'

import { Subscription } from 'rxjs'


const MAX_ALERTS = 5


@Component({
  selector: 'pngx-warehouse-tree-widget',
  templateUrl: './warehouse-tree-widget.component.html',
  styleUrls: ['./warehouse-tree-widget.component.scss'],
})

export class WarehouseTreeWidgetComponent extends ComponentWithPermissions
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

  @Output() goToNode = new EventEmitter<any>()
  data = []
  totalElement = 0
  pageNumber: number = 1
  nodeId: number = 0
  subscription: Subscription

  renderNode(c, object, event) {
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
      const node = this.viewContainer.createComponent(WarehouseTreeWidgetComponent)
      node.instance.data = c.results
      node.instance.nodeId = object.id
      node.instance.totalElement = c.count
      node.instance.goToNode.subscribe((object) => {
        this.goToNode.emit(object)
      })
      const componentElement = node.location.nativeElement
      this.renderer.appendChild(tdElement, componentElement)
      return
    }

  }

  getNode(object: Folder, event) {

    this.folderService.listFolderFiltered(
      1,
      null,
      null,
      true,
      object.id,
      null,
      true,
    ).subscribe((c) => {
      this.renderNode(c, object, event)
    })

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
    this.folderService.listFolderFiltered(
      this.pageNumber,
      null,
      null,
      true,
      this.nodeId,
      null,
      true,
    ).subscribe((c) => {
      this.data = this.data.concat(c.results)

    })

  }

  reload() {
    console.log(this.nodeId)
    if (this.nodeId == 0) {
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
          this.data = this.data.concat(c.results)
          this.isLoading = false
          this.loading = false
          return
        }
        this.data = c.results
        this.totalElement = c.count
        this.isLoading = false
        this.loading = false
        return
      })
    }
  }
}
