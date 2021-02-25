import { TestBed } from '@angular/core/testing';

import { ApiVersionInterceptor } from './api-version.interceptor';

describe('ApiVersionInterceptor', () => {
  beforeEach(() => TestBed.configureTestingModule({
    providers: [
      ApiVersionInterceptor
      ]
  }));

  it('should be created', () => {
    const interceptor: ApiVersionInterceptor = TestBed.inject(ApiVersionInterceptor);
    expect(interceptor).toBeTruthy();
  });
});
