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

  @Input() data: any[] = [] // Nhận dữ liệu cây thư mục từ component chính
  @Output() contentUpdated = new EventEmitter<string>() // Sự kiện để phát ra nội dung
  isLoading: boolean = false


  // Hàm gọi khi nhấn vào thư mục hoặc file
  goToFolder(object: Folder, event) {

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
      console.log('ko co du lieu')
      if(c.count > 0) {
        const tdElement = (event.target as HTMLElement).closest('td')
        const node = this.viewContainer.createComponent(NodeFileWidgetComponent)
        node.instance.data = c.results
        const componentElement = node.location.nativeElement
        this.renderer.appendChild(tdElement, componentElement)
        return
      }


    })

  }
}
