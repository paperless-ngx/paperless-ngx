import { Component, Input, Output, EventEmitter, ViewContainerRef, Renderer2 } from '@angular/core'
import { Folder } from '../../../../data/folder'
import { HttpClient } from '@angular/common/http'
import { FolderService } from '../../../../services/rest/folder.service'
import { DocumentListViewService } from '../../../../services/document-list-view.service'

@Component({
  selector: 'node-tree-widget',
  templateUrl: './node-tree-widget.component.html',
  styleUrls: ['./node-tree-widget.component.scss'],
})
export class NodeFileWidgetComponent {
  constructor(
    private http: HttpClient,
    private folderService: FolderService,
    private viewContainer: ViewContainerRef,
    private renderer: Renderer2,
  ) {
  }

  data: any[] = [] // Nhận dữ liệu cây thư mục từ component chính
  @Input() elementId: number = 0 // Nhận dữ liệu cây thư mục từ component chính
  @Output() goToNode = new EventEmitter<any>()
  isLoading: boolean = false
  totalElement = 0;
  pageNumber: number = 1

  renderNode(c,object,event){
    const spanElement = (event.target as HTMLElement).closest('span')
      const tdElement = spanElement.closest('td')
      const svgElement = spanElement?.querySelector('svg')
      const tableElement = tdElement?.querySelector('table');
      if (svgElement.style.transform!='') {
          this.renderer.removeStyle(svgElement, 'transform')
      }
      else {
        this.renderer.setStyle(svgElement, 'transform', 'rotate(90deg)')
        this.renderer.setStyle(svgElement, 'transition', 'transform 0.3s ease')
      }
      if (tableElement) {
        this.renderer.removeChild(tableElement.parentNode, tableElement);
        return;
      }
      if(c.count > 0) {
        const tdElement = (event.target as HTMLElement).closest('td')
        const node = this.viewContainer.createComponent(NodeFileWidgetComponent)
        node.instance.goToNode.subscribe((object) => {this.goToNode.emit(object)})
        node.instance.elementId = object.id
        node.instance.totalElement = c.count
        node.instance.data = c.results
        const componentElement = node.location.nativeElement
        this.renderer.appendChild(tdElement, componentElement)
        return
      }
  }
  // Hàm gọi khi nhấn vào thư mục hoặc file
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
      this.renderNode(c,object,event)
    })

  }
  viewMore() {
    this.pageNumber=this.pageNumber+1
    this.folderService.listFolderFiltered(
      this.pageNumber,
      null,
      null,
      true,
      this.elementId,
      null,
      true,
    ).subscribe((c) => {
      this.data = this.data.concat(c.results)

    })
  }
}
