import { TestBed } from '@angular/core/testing';

import { CsrfInterceptor } from './csrf.interceptor';

describe('CsrfInterceptor', () => {
  beforeEach(() => TestBed.configureTestingModule({
    providers: [
      CsrfInterceptor
      ]
  }));

  it('should be created', () => {
    const interceptor: CsrfInterceptor = TestBed.inject(CsrfInterceptor);
    expect(interceptor).toBeTruthy();
  });
});
