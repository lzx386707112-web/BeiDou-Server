package org.gms.config;

import com.alibaba.druid.pool.DruidDataSource;
import com.mybatisflex.core.mybatis.FlexConfiguration;
import com.mybatisflex.spring.FlexSqlSessionFactoryBean;
import com.mybatisflex.spring.boot.SpringBootVFS;
import org.apache.ibatis.session.SqlSessionFactory;
import org.mybatis.spring.SqlSessionTemplate;
import org.springframework.boot.autoconfigure.condition.ConditionalOnMissingBean;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.core.env.Environment;

import javax.sql.DataSource;

@Configuration(proxyBeanMethods = false)
public class MybatisFlexFallbackConfig {

    @Bean
    @ConditionalOnMissingBean(DataSource.class)
    public DataSource fallbackDataSource(Environment environment) {
        DruidDataSource dataSource = new DruidDataSource();
        dataSource.setDriverClassName(environment.getProperty("mybatis-flex.datasource.mysql.driver-class-name"));
        dataSource.setUrl(environment.getProperty("mybatis-flex.datasource.mysql.url"));
        dataSource.setUsername(environment.getProperty("mybatis-flex.datasource.mysql.username"));
        dataSource.setPassword(environment.getProperty("mybatis-flex.datasource.mysql.password"));
        return dataSource;
    }

    @Bean
    @ConditionalOnMissingBean(SqlSessionFactory.class)
    public SqlSessionFactory fallbackSqlSessionFactory(DataSource dataSource) throws Exception {
        FlexSqlSessionFactoryBean factoryBean = new FlexSqlSessionFactoryBean();
        factoryBean.setDataSource(dataSource);
        factoryBean.setVfs(SpringBootVFS.class);
        factoryBean.setConfiguration(new FlexConfiguration());
        return factoryBean.getObject();
    }

    @Bean
    @ConditionalOnMissingBean(SqlSessionTemplate.class)
    public SqlSessionTemplate fallbackSqlSessionTemplate(SqlSessionFactory sqlSessionFactory) {
        return new SqlSessionTemplate(sqlSessionFactory);
    }
}
