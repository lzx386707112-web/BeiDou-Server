package orange.wz.config;

import jakarta.annotation.Nonnull;
import org.springframework.context.annotation.Configuration;
import org.springframework.core.io.Resource;
import org.springframework.web.servlet.config.annotation.ResourceHandlerRegistry;
import org.springframework.web.servlet.config.annotation.WebMvcConfigurer;
import org.springframework.web.servlet.resource.PathResourceResolver;

import java.io.IOException;

@Configuration
public class WebMvcConfig implements WebMvcConfigurer {

    @Override
    public void addResourceHandlers(ResourceHandlerRegistry registry) {
        // 处理Vue路由的SPA特性
        // registry.addResourceHandler("/**")
        //         .addResourceLocations("classpath:/static/")
        //         .resourceChain(true)
        //         .addResolver(new PathResourceResolver() {
        //             @Override
        //             protected Resource getResource(@Nonnull String resourcePath, @Nonnull Resource location) throws IOException {
        //                 Resource requestedResource = location.createRelative(resourcePath);
        //                 // 如果请求的文件不存在，返回index.html
        //                 return requestedResource.exists() && requestedResource.isReadable() ?
        //                         requestedResource :
        //                         location.createRelative("index.html");
        //             }
        //         });
    }
}
