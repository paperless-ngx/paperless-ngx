import { Pipe, PipeTransform } from '@angular/core';
import { DomSanitizer } from '@angular/platform-browser';

@Pipe({
  name: 'safe'
})
export class SafePipe implements PipeTransform {

  constructor(private sanitizer: DomSanitizer) { }

  transform(url) {
    if (url == null) {
      return this.sanitizer.bypassSecurityTrustResourceUrl("")
    } else {
      return this.sanitizer.bypassSecurityTrustResourceUrl(url);
    }
  }

}
