import { Directive, ElementRef, Renderer2, HostListener, OnInit, OnDestroy } from '@angular/core';

@Directive({
  selector: '[pngxPreventRightClick]',
})
export class PreventRightClickDirective implements OnInit, OnDestroy {

  private selectedIds: Set<string> = new Set();
  private mutationObserver: MutationObserver;

  constructor(private el: ElementRef, private renderer: Renderer2) {
    this.mutationObserver = new MutationObserver((mutations) => {
      mutations.forEach((mutation) => {
        if (mutation.type === 'childList') {
          mutation.addedNodes.forEach((node) => {
            if (node instanceof HTMLElement && node.classList.contains('document-container')) {
              this.addContextMenuListener(node);
            }
          });
        }
      });
    });
  }

  ngOnInit(): void {
    this.observeDOMChanges();
    // Adding listener to existing document-container elements, if any
    const existingDocumentContainers = document.querySelectorAll('.document-container') as NodeListOf<HTMLElement>;
    existingDocumentContainers.forEach(documentContainer => {
      this.addContextMenuListener(documentContainer);
    });
  }

  ngOnDestroy(): void {
    this.mutationObserver.disconnect();
  }

  private observeDOMChanges(): void {
    this.mutationObserver.observe(document.body, {
      childList: true,
      subtree: true
    });
  }

  private addContextMenuListener(element: HTMLElement): void {
    this.renderer.listen(element, 'contextmenu', (event: MouseEvent) => {
      this.onContextMenu(event);
    });
  }

  @HostListener('contextmenu', ['$event'])
  onContextMenu(event: MouseEvent): void {
    event.preventDefault();

    const target = event.target as HTMLElement;
    const folderCha = target.closest('.folder-cha') as HTMLElement;
    const trElement = target.closest('tr') as HTMLElement;
    const folderLeft = target.closest('.folder-left') as HTMLElement;
    const folderRightContent = target.closest('.folder-right-conten') as HTMLElement;
    const documentContainer = target.closest('.document-container') as HTMLElement;

    // Hide custom elements if clicked outside their respective areas
    if (!folderCha && !trElement) {
      this.hideCustomElement('.c');
    }
    if (!documentContainer) {
      this.hideCustomElement('.f');
    }
    if (documentContainer) {
      const documentElement = documentContainer.closest('.document') as HTMLElement;
      if (documentElement) {
        const documentId = documentElement.getAttribute('data-document-id');
        if (!isNaN(Number(documentId))) {
          console.log(`Clicked on document with ID: ${documentId}`);
          this.updateChuaAttribute('.f', documentId);
          this.showCustomContextMenu(event.clientX, event.clientY);
          this.showCustomElement('.f', event.clientX, event.clientY); 
        } else {
          console.error('data-document-id attribute not found or is not a number.');
        }
      } else {
        console.error('.document element not found for .document-container.');
      }
    }

    if (folderRightContent && !trElement) {
      const idKhai = folderRightContent.getAttribute('id-khai');
      this.updateAddAttribute('.id', idKhai || '');
      this.showCustomContextMenu(event.clientX, event.clientY);
    } else if (folderCha) {
      const folderElement = folderCha.closest('.folder') as HTMLElement;
      if (folderElement) {
        const folderId = folderElement.getAttribute('data-folder-id');
        this.updateAddAttribute('.id', folderId || '');
        this.showCustomContextMenu(event.clientX, event.clientY);
        this.showCustomElement('.c', event.clientX, event.clientY);
      } else {
        console.error('Parent folder element not found.');
      }
    } else if (trElement) {
      const folderId = trElement.getAttribute('data-folder-id');
      if (!isNaN(Number(folderId))) {
        this.updateAddAttribute('.id', folderId);
        this.showCustomContextMenu(event.clientX, event.clientY);
        this.showCustomElement('.c', event.clientX, event.clientY);
      } else {
        console.error('data-folder-id attribute not found or is not a number.');
      }
    } else if (folderLeft) {
      this.updateAddAttribute('.id', '');
      this.showCustomContextMenu(event.clientX, event.clientY);
    } else if (documentContainer) {
      const documentElement = documentContainer.closest('.document') as HTMLElement;
      if (documentElement) {
        const documentId = documentElement.getAttribute('data-document-id');
        if (!isNaN(Number(documentId))) {
          this.updateAddAttribute('.id', documentId);
          this.showCustomContextMenu(event.clientX, event.clientY);
          this.showCustomElement('.f', event.clientX, event.clientY);
        } else {
          console.error('data-document-id attribute not found or is not a number.');
        }
      } else {
        console.error('.document element not found for .document-container.');
      }
    } else {
      console.error('folder-cha, folder-left, tr, or document-container element not found.');
    }
    this.updateAdd2Attribute('.id');
    this.showCustomContextMenu(event.clientX, event.clientY);
  }

  @HostListener('click', ['$event'])
  onClick(event: MouseEvent): void {
    const target = event.target as HTMLElement;
    const trElement = target.closest('tr') as HTMLElement;

    if (trElement && event.ctrlKey) {
      const folderId = trElement.getAttribute('data-folder-id');
      if (folderId) {
        this.toggleSelection(folderId);
      }
    } else {
      // Reset selections if clicked outside
      this.selectedIds.clear();
      this.updateAdd2Attribute('.id');
    }
  }
  private updateChuaAttribute(selector: string, id: string): void {
    const listItems = this.el.nativeElement.querySelectorAll(selector) as NodeListOf<HTMLElement>;
    listItems.forEach(listItem => {
      this.renderer.setAttribute(listItem, 'chua', id);
    });
  }
  private updateAddAttribute(selector: string, id: string): void {
    const listItems = document.querySelectorAll(selector) as NodeListOf<HTMLElement>;
    listItems.forEach(listItem => {
      listItem.setAttribute('add', id);
    });
  }
  private toggleSelection(folderId: string): void {
    if (this.selectedIds.has(folderId)) {
      this.selectedIds.delete(folderId);
    } else {
      this.selectedIds.add(folderId);
    }
  }
  private showCustomElement(selector: string, x: number, y: number): void {
    const elements = document.querySelectorAll(selector);
    elements.forEach((element) => {
      const customElement = element as HTMLElement;
      this.renderer.setStyle(customElement, 'display', 'block');
      this.renderer.setStyle(customElement, 'left', `${x}px`);
      this.renderer.setStyle(customElement, 'top', `${y}px`);
    });
  }
  private updateAdd2Attribute(selector: string): void {
    const listItems = document.querySelectorAll(selector) as NodeListOf<HTMLElement>;
    listItems.forEach(listItem => {
      listItem.setAttribute('add2', Array.from(this.selectedIds).join(','));
    });
  }
  private hideCustomElement(selector: string): void {
    const elements = document.querySelectorAll(selector);
    if (elements) {
      elements.forEach((element) => {
        this.renderer.setStyle(element, 'display', 'none');
      });
    }
  }
  private showCustomContextMenu(x: number, y: number): void {
    const customContextMenu = document.querySelector('#contextMenu') as HTMLElement;
    if (customContextMenu) {
      this.renderer.setStyle(customContextMenu, 'display', 'block');
      this.renderer.setStyle(customContextMenu, 'left', `${x}px`);
      this.renderer.setStyle(customContextMenu, 'top', `${y}px`);
    }
  }
}
